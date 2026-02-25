"""コードAPI・階層APIサービス。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any

import httpx

from bojstat.cache import FileCache
import warnings

from bojstat.config import NORMALIZER_VERSION, PARSER_VERSION, SCHEMA_VERSION, ClientConfig, RetryConfig
from bojstat.enums import DB, ConsistencyMode, Frequency, Format, Lang, OutputOrder
from bojstat.errors import BojConsistencyError, BojDateParseError
from bojstat.models import MetadataFrame, TimeSeriesFrame
from bojstat.normalize import expand_timeseries_rows
from bojstat.pager.code_pager import CodePagerState, advance_code_position
from bojstat.pager.layer_pager import LayerPagerState, advance_layer_position
from bojstat.resume import build_request_fingerprint, create_resume_token, decode_resume_token, validate_resume_token
from bojstat.services._transport import perform_async_request, perform_sync_request
from bojstat.types import ResponseMeta, TimeSeriesRecord
from bojstat.validation import (
    canonical_params,
    guess_frequency_from_code,
    normalize_code_periods,
    normalize_codes,
    normalize_db,
    normalize_format,
    normalize_frequency,
    normalize_lang,
    normalize_layer,
    normalize_periods,
    normalize_raw_params,
    split_codes_by_frequency_and_size,
    validate_strict_auto_split,
)

_JST = ZoneInfo("Asia/Tokyo")


def _resolve_codes_from_metadata(
    metadata_frame: MetadataFrame,
    frequency: Frequency,
) -> list[str]:
    """メタデータから指定期種の系列コードを抽出する。

    guess_frequency_from_code() でコード文字列から期種を推定するため、
    メタデータの言語（lang）に依存しない。

    Args:
        metadata_frame: メタデータフレーム。
        frequency: 正規化済み Frequency enum。normalize_frequency() の戻り値を期待する。

    Returns:
        系列コード一覧。該当コードがない場合は空リスト。
    """
    result: list[str] = []
    for record in metadata_frame.records:
        if not record.series_code:
            continue
        guessed = guess_frequency_from_code(record.series_code)
        if guessed == frequency.value or guessed == "UNKNOWN":
            result.append(record.series_code)
    return result


def _should_resolve_wildcard(
    *,
    config: ClientConfig,
    resolve_wildcard: bool | None,
    layer_norm: list[str],
    auto_paginate: bool,
    resume_token: str | None,
    start_position: int | None,
) -> bool:
    """ワイルドカード解決パスに入るべきかを判定する。

    同期・非同期で完全に同一のロジックを共有するためスタンドアロン関数とする。
    metadata_service の有無は呼び出し元で事前にチェックする。

    Args:
        config: クライアント設定。
        resolve_wildcard: メソッドレベルのオーバーライド値。
        layer_norm: 正規化済みlayer値。
        auto_paginate: 自動ページング有効か。
        resume_token: リジュームトークン。
        start_position: 開始位置。

    Returns:
        ワイルドカード解決パスに入るべきならTrue。
    """
    resolve_mode = config.resolve_wildcard if resolve_wildcard is None else resolve_wildcard
    # NOTE: 部分ワイルドカード（"*" in layer_norm）対応時は
    # layer_norm == ["*"] を "*" in layer_norm に変更し、
    # _resolve_codes_from_metadata に layer フィルタロジックを追加する。
    return (
        resolve_mode
        and layer_norm == ["*"]
        and auto_paginate
        and not resume_token
        and not start_position
    )


class DataService:
    """同期データ取得サービス。"""

    def __init__(
        self,
        *,
        client: httpx.Client,
        config: ClientConfig,
        retry_config: RetryConfig,
        cache: FileCache,
        limiter: Any,
        metadata_service: Any = None,
    ) -> None:
        self._client = client
        self._config = config
        self._retry_config = retry_config
        self._cache = cache
        self._limiter = limiter
        self._metadata_service = metadata_service

    def get_by_code(
        self,
        *,
        db: DB | str,
        code: str | Sequence[str],
        start: str | None = None,
        end: str | None = None,
        start_position: int | None = None,
        lang: Lang | str | None = None,
        format: Format | str | None = None,
        strict_api: bool | None = None,
        auto_split_codes: bool | None = None,
        raw_params: Mapping[str, str] | None = None,
        resume_token: str | None = None,
        output_order: OutputOrder | str | None = None,
    ) -> TimeSeriesFrame:
        """コードAPIで時系列データを取得する。"""

        strict_mode = self._config.strict_api if strict_api is None else strict_api
        split_mode = self._config.auto_split_codes if auto_split_codes is None else auto_split_codes
        validate_strict_auto_split(strict_api=strict_mode, auto_split_codes=split_mode)

        lang_norm = normalize_lang(lang or self._config.lang)
        format_norm = normalize_format(format or self._config.format)
        db_norm = normalize_db(db)
        codes = normalize_codes(code)
        raw = normalize_raw_params(
            dict(raw_params) if raw_params is not None else None,
            allow_raw_override=self._config.allow_raw_override,
        )

        start_norm, end_norm = normalize_code_periods(start=start, end=end)

        if strict_mode or not split_mode:
            chunks = [codes]
        else:
            chunks = split_codes_by_frequency_and_size(codes, chunk_size=250)

        code_order_map = {item: idx for idx, item in enumerate(codes)}
        endpoint = "/getDataCode"
        output_order_norm = (
            output_order
            if isinstance(output_order, OutputOrder)
            else OutputOrder(output_order or self._config.output_order)
        )

        fingerprint_components: dict[str, Any] = {
            "api_origin": self._config.base_url,
            "endpoint": endpoint,
            "db": db_norm,
            "code": codes,
            "start": start_norm,
            "end": end_norm,
            "strict_api": strict_mode,
            "auto_split_codes": split_mode,
            "lang": lang_norm.value,
            "format": format_norm.value,
            "parser_version": PARSER_VERSION,
            "normalizer_version": NORMALIZER_VERSION,
            "schema_version": SCHEMA_VERSION,
            "output_order": output_order_norm.value,
            "raw_params": canonical_params(raw),
        }
        fingerprint = build_request_fingerprint(fingerprint_components)

        start_chunk_index = 0
        chunk_start_position = start_position or 1
        if resume_token:
            token_state = decode_resume_token(resume_token)
            validate_resume_token(
                token_state,
                request_fingerprint=fingerprint,
                chunk_index=token_state.chunk_index,
                parser_version=PARSER_VERSION,
                normalizer_version=NORMALIZER_VERSION,
            )
            start_chunk_index = token_state.chunk_index
            chunk_start_position = token_state.next_position
            code_order_map = token_state.code_order_map

        cache_key = self._build_cache_key("code", fingerprint, lang_norm, format_norm)
        cache_hit = self._cache.get(key=cache_key, mode=self._config.cache.mode)
        if cache_hit and not cache_hit.stale:
            return TimeSeriesFrame.from_cache_payload(cache_hit.payload["payload"])  # type: ignore[arg-type]

        dedupe: dict[tuple[str, str], TimeSeriesRecord] = {}
        last_meta: ResponseMeta | None = None
        conflicts_sample: list[dict[str, Any]] = []
        conflicts_count = 0

        for chunk_index, chunk in enumerate(chunks):
            if chunk_index < start_chunk_index:
                continue
            pager = CodePagerState(
                chunk_index=chunk_index,
                start_position=chunk_start_position if chunk_index == start_chunk_index else 1,
            )
            page_index = 0
            while True:
                params = {
                    "DB": db_norm,
                    "CODE": ",".join(chunk),
                    "LANG": lang_norm.value,
                    "FORMAT": format_norm.value,
                }
                if pager.start_position > 1:
                    params["STARTPOSITION"] = str(pager.start_position)
                if start_norm:
                    params["STARTDATE"] = start_norm
                if end_norm:
                    params["ENDDATE"] = end_norm
                params.update(raw)

                parsed, request_url, _ = perform_sync_request(
                    client=self._client,
                    endpoint=endpoint,
                    params=params,
                    lang=lang_norm,
                    format=format_norm,
                    retry_config=self._retry_config,
                    limiter=self._limiter,
                    user_agent=self._config.user_agent,
                    capture_full_response=self._config.capture_full_response,
                )

                if parsed.date_parse_warning and self._config.metadata_freshness_strict:
                    raise BojDateParseError(parsed.date_parse_warning)

                if parsed.status == 400 and parsed.message_id == "M181007E" and strict_mode:
                    # strict modeでは公式エラーを透過させる。
                    pass

                records = expand_timeseries_rows(
                    parsed.rows,
                    source_page_index=page_index,
                    code_order_map=code_order_map,
                )
                for record in records:
                    key = (record.series_code, record.survey_date)
                    existing = dedupe.get(key)
                    if existing is None:
                        dedupe[key] = record
                        continue
                    if existing.last_update != record.last_update:
                        conflicts_count += 1
                        conflicts_sample.append(
                            {
                                "series_code": record.series_code,
                                "survey_date": record.survey_date,
                                "existing_last_update": existing.last_update,
                                "incoming_last_update": record.last_update,
                            }
                        )
                        if self._config.consistency_mode == ConsistencyMode.STRICT:
                            raise BojConsistencyError(
                                signal="last_update_conflict",
                                details=conflicts_sample[-1],
                            )
                    dedupe[key] = _choose_record(existing, record)

                next_position = parsed.next_position
                current_resume = create_resume_token(
                    api="code",
                    api_origin=self._config.base_url,
                    request_fingerprint=fingerprint,
                    chunk_index=chunk_index,
                    next_position=next_position or 1,
                    lang=lang_norm.value,
                    format=format_norm.value,
                    parser_version=PARSER_VERSION,
                    normalizer_version=NORMALIZER_VERSION,
                    schema_version=SCHEMA_VERSION,
                    code_order_map=code_order_map,
                )
                last_meta = ResponseMeta(
                    status=parsed.status,
                    message_id=parsed.message_id,
                    message=parsed.message,
                    date_raw=parsed.date_raw,
                    date_parsed=parsed.date_parsed,
                    date_parse_warning=parsed.date_parse_warning,
                    date_semantics="output_file_created_at",
                    next_position=parsed.next_position,
                    parameters=parsed.parameters,
                    request_url=request_url,
                    schema_version=SCHEMA_VERSION,
                    parser_version=PARSER_VERSION,
                    normalizer_version=NORMALIZER_VERSION,
                    resume_token=current_resume,
                    conflicts_count=conflicts_count,
                    conflicts_sample=conflicts_sample[:20],
                )
                page_index += 1
                if not advance_code_position(state=pager, next_position=next_position):
                    break

        records_sorted = _sort_records(
            list(dedupe.values()),
            output_order=output_order_norm,
        )
        meta = last_meta or _empty_meta(request_url="")
        if meta.next_position is None:
            meta.resume_token = None
        frame = TimeSeriesFrame(records=records_sorted, meta=meta)
        self._cache.put(key=cache_key, payload=frame.to_cache_payload(), complete=True)
        return frame

    def get_by_layer(
        self,
        *,
        db: DB | str,
        frequency: str,
        layer: str | Sequence[str | int],
        start: str | None = None,
        end: str | None = None,
        start_position: int | None = None,
        lang: Lang | str | None = None,
        format: Format | str | None = None,
        auto_paginate: bool = True,
        raw_params: Mapping[str, str] | None = None,
        resume_token: str | None = None,
        resolve_wildcard: bool | None = None,
    ) -> TimeSeriesFrame:
        """階層APIで時系列データを取得する。"""

        lang_norm = normalize_lang(lang or self._config.lang)
        format_norm = normalize_format(format or self._config.format)
        db_norm = normalize_db(db)
        freq_norm = normalize_frequency(frequency, required=True)
        assert freq_norm is not None
        layer_norm = normalize_layer(layer)
        start_norm, end_norm = normalize_periods(
            start=start,
            end=end,
            frequency=freq_norm,
        )
        raw = normalize_raw_params(
            dict(raw_params) if raw_params is not None else None,
            allow_raw_override=self._config.allow_raw_override,
        )

        needs_resolve = (
            self._metadata_service is not None
            and _should_resolve_wildcard(
                config=self._config,
                resolve_wildcard=resolve_wildcard,
                layer_norm=layer_norm,
                auto_paginate=auto_paginate,
                resume_token=resume_token,
                start_position=start_position,
            )
        )

        endpoint = "/getDataLayer"
        fingerprint = build_request_fingerprint(
            {
                "api_origin": self._config.base_url,
                "endpoint": endpoint,
                "db": db_norm,
                "layer": layer_norm,
                "frequency": freq_norm.value,
                "start": start_norm,
                "end": end_norm,
                "lang": lang_norm.value,
                "format": format_norm.value,
                "consistency_mode": self._config.consistency_mode.value,
                "conflict_resolution": self._config.conflict_resolution.value,
                "parser_version": PARSER_VERSION,
                "normalizer_version": NORMALIZER_VERSION,
                "schema_version": SCHEMA_VERSION,
                "raw_params": canonical_params(raw),
            }
        )

        resolve_mode = self._config.resolve_wildcard if resolve_wildcard is None else resolve_wildcard
        cache_key = self._build_cache_key(
            "layer", fingerprint, lang_norm, format_norm,
            resolve_wildcard=resolve_mode,
        )
        cache_hit = self._cache.get(key=cache_key, mode=self._config.cache.mode)
        if cache_hit and not cache_hit.stale:
            return TimeSeriesFrame.from_cache_payload(cache_hit.payload["payload"])  # type: ignore[arg-type]

        if needs_resolve:
            result = self._get_by_layer_via_codes(
                db=db_norm, frequency=freq_norm,
                start=start_norm, end=end_norm,
                lang=lang_norm, format=format_norm,
                raw=raw, cache_key=cache_key,
            )
            if result is not None:
                return result

        pager = LayerPagerState(start_position=start_position or 1)
        if resume_token:
            token_state = decode_resume_token(resume_token)
            validate_resume_token(
                token_state,
                request_fingerprint=fingerprint,
                chunk_index=0,
                parser_version=PARSER_VERSION,
                normalizer_version=NORMALIZER_VERSION,
            )
            pager.start_position = token_state.next_position

        dedupe: dict[tuple[str, str], TimeSeriesRecord] = {}
        conflicts_count = 0
        conflicts_sample: list[dict[str, Any]] = []
        window_signal: str | None = None
        first_fetch = datetime.now(tz=_JST)
        page_index = 0
        last_meta: ResponseMeta | None = None
        code_order_map: dict[str, int] = {}

        while True:
            params: dict[str, str] = {
                "DB": db_norm,
                "FREQUENCY": freq_norm.value,
                "LANG": lang_norm.value,
                "FORMAT": format_norm.value,
                "LAYER": ",".join(layer_norm),
            }
            if pager.start_position > 1:
                params["STARTPOSITION"] = str(pager.start_position)
            if start_norm:
                params["STARTDATE"] = start_norm
            if end_norm:
                params["ENDDATE"] = end_norm
            params.update(raw)

            parsed, request_url, _ = perform_sync_request(
                client=self._client,
                endpoint=endpoint,
                params=params,
                lang=lang_norm,
                format=format_norm,
                retry_config=self._retry_config,
                limiter=self._limiter,
                user_agent=self._config.user_agent,
                capture_full_response=self._config.capture_full_response,
            )

            now = datetime.now(tz=_JST)
            if _window_crossed(first_fetch=first_fetch, current=now):
                window_signal = "window_crossed"
                if self._config.consistency_mode == ConsistencyMode.STRICT:
                    raise BojConsistencyError(
                        signal="window_crossed",
                        details={"first_fetch": first_fetch.isoformat(), "current": now.isoformat()},
                    )

            records = expand_timeseries_rows(
                parsed.rows,
                source_page_index=page_index,
                code_order_map=code_order_map,
            )
            for record in records:
                if record.series_code not in code_order_map:
                    code_order_map[record.series_code] = len(code_order_map)
                    record.original_code_index = code_order_map[record.series_code]
                key = (record.series_code, record.survey_date)
                existing = dedupe.get(key)
                if existing is None:
                    dedupe[key] = record
                    continue
                if existing.last_update != record.last_update:
                    conflicts_count += 1
                    detail = {
                        "series_code": record.series_code,
                        "survey_date": record.survey_date,
                        "existing_last_update": existing.last_update,
                        "incoming_last_update": record.last_update,
                    }
                    conflicts_sample.append(detail)
                    if self._config.consistency_mode == ConsistencyMode.STRICT:
                        raise BojConsistencyError(signal="last_update_conflict", details=detail)
                dedupe[key] = _choose_record(existing, record)

            current_resume = create_resume_token(
                api="layer",
                api_origin=self._config.base_url,
                request_fingerprint=fingerprint,
                chunk_index=0,
                next_position=parsed.next_position or 1,
                lang=lang_norm.value,
                format=format_norm.value,
                parser_version=PARSER_VERSION,
                normalizer_version=NORMALIZER_VERSION,
                schema_version=SCHEMA_VERSION,
                code_order_map=code_order_map,
            )

            last_meta = ResponseMeta(
                status=parsed.status,
                message_id=parsed.message_id,
                message=parsed.message,
                date_raw=parsed.date_raw,
                date_parsed=parsed.date_parsed,
                date_parse_warning=parsed.date_parse_warning,
                date_semantics="output_file_created_at",
                next_position=parsed.next_position,
                parameters=parsed.parameters,
                request_url=request_url,
                schema_version=SCHEMA_VERSION,
                parser_version=PARSER_VERSION,
                normalizer_version=NORMALIZER_VERSION,
                resume_token=current_resume,
                consistency_signal=window_signal,
                conflicts_count=conflicts_count,
                conflicts_sample=conflicts_sample[:20],
            )

            page_index += 1
            if not auto_paginate:
                break
            if not advance_layer_position(state=pager, next_position=parsed.next_position):
                break

        records_sorted = _sort_records(
            list(dedupe.values()),
            output_order=self._config.output_order,
        )
        meta = last_meta or _empty_meta(request_url="")
        if meta.next_position is None:
            meta.resume_token = None

        frame = TimeSeriesFrame(records=records_sorted, meta=meta)
        self._cache.put(key=cache_key, payload=frame.to_cache_payload(), complete=True)
        return frame

    def _get_by_layer_via_codes(
        self,
        *,
        db: str,
        frequency: Frequency,
        start: str | None,
        end: str | None,
        lang: Lang,
        format: Format,
        raw: dict[str, str],
        cache_key: str,
    ) -> TimeSeriesFrame | None:
        """階層ワイルドカードをメタデータ経由でコードAPIへ委譲する。

        内部で get_by_code(auto_split_codes=True) に委譲するため、
        Code API チャンク単位のキャッシュも保存される（二重キャッシュ）。

        Args:
            db: 正規化済みDB。
            frequency: 正規化済み期種。
            start: 開始期間。
            end: 終了期間。
            lang: 正規化済み言語。
            format: 正規化済みフォーマット。
            raw: raw_params。
            cache_key: Layer API用キャッシュキー。

        Returns:
            TimeSeriesFrame、またはメタデータ取得失敗時は None。
        """
        resolve_url = f"bojstat://resolve-wildcard/{db}?layer=*&frequency={frequency.value}"
        first_fetch = datetime.now(tz=_JST)

        try:
            meta_frame = self._metadata_service.get(db=db, lang=Lang.JP)
        except Exception:
            warnings.warn(
                f"メタデータ取得に失敗したため Layer API に直接アクセスします: db={db}",
                stacklevel=2,
            )
            return None

        codes = _resolve_codes_from_metadata(meta_frame, frequency)
        if not codes:
            empty = TimeSeriesFrame(
                records=[],
                meta=_empty_meta(request_url=resolve_url),
            )
            self._cache.put(key=cache_key, payload=empty.to_cache_payload(), complete=True)
            return empty

        # get_by_code は内部でチャンク単位のキャッシュを保存するため、
        # strict モードの window_crossed チェックを先に行い、
        # キャッシュ汚染を防ぐ。
        pre_code = datetime.now(tz=_JST)
        if _window_crossed(first_fetch=first_fetch, current=pre_code):
            if self._config.consistency_mode == ConsistencyMode.STRICT:
                raise BojConsistencyError(
                    signal="window_crossed",
                    details={
                        "first_fetch": first_fetch.isoformat(),
                        "current": pre_code.isoformat(),
                    },
                )

        frame = self.get_by_code(
            db=db, code=codes,
            start=start, end=end,
            lang=lang, format=format,
            strict_api=False,
            auto_split_codes=True,
            raw_params=raw if raw else None,
        )

        now = datetime.now(tz=_JST)
        if _window_crossed(first_fetch=first_fetch, current=now):
            if self._config.consistency_mode == ConsistencyMode.STRICT:
                raise BojConsistencyError(
                    signal="window_crossed",
                    details={
                        "first_fetch": first_fetch.isoformat(),
                        "current": now.isoformat(),
                    },
                )
            if frame.meta:
                frame.meta.consistency_signal = "window_crossed"

        if frame.meta:
            frame.meta.request_url = resolve_url

        self._cache.put(key=cache_key, payload=frame.to_cache_payload(), complete=True)
        return frame

    def _build_cache_key(
        self,
        api: str,
        fingerprint: str,
        lang: Lang,
        format: Format,
        *,
        resolve_wildcard: bool | None = None,
    ) -> str:
        base = (
            f"api={api}|origin={self._config.base_url}|lang={lang.value}|format={format.value}|"
            f"parser={PARSER_VERSION}|normalizer={NORMALIZER_VERSION}|schema={SCHEMA_VERSION}|"
            f"strict_api={self._config.strict_api}|auto_split={self._config.auto_split_codes}|"
            f"consistency={self._config.consistency_mode.value}|"
            f"conflict={self._config.conflict_resolution.value}|"
            f"output_order={self._config.output_order.value}"
        )
        if resolve_wildcard is not None:
            base += f"|resolve_wildcard={resolve_wildcard}"
        base += f"|fp={fingerprint}"
        return base


class AsyncDataService:
    """非同期データ取得サービス。"""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        config: ClientConfig,
        retry_config: RetryConfig,
        cache: FileCache,
        limiter: Any,
        metadata_service: Any = None,
    ) -> None:
        self._client = client
        self._config = config
        self._retry_config = retry_config
        self._cache = cache
        self._limiter = limiter
        self._metadata_service = metadata_service

    async def get_by_code(self, **kwargs: Any) -> TimeSeriesFrame:
        """同期実装互換の非同期版。"""

        return await _run_data_service_async(self._get_by_code_impl(**kwargs))

    async def _get_by_code_impl(self, **kwargs: Any) -> TimeSeriesFrame:
        sync = _AsyncBridge(self)
        return await sync.get_by_code(**kwargs)

    async def get_by_layer(self, **kwargs: Any) -> TimeSeriesFrame:
        """同期実装互換の非同期版。"""

        return await _run_data_service_async(self._get_by_layer_impl(**kwargs))

    async def _get_by_layer_impl(self, **kwargs: Any) -> TimeSeriesFrame:
        sync = _AsyncBridge(self)
        return await sync.get_by_layer(**kwargs)


class _AsyncBridge:
    """同期ロジックを非同期トランスポートで再利用する橋渡し。"""

    def __init__(self, owner: AsyncDataService) -> None:
        self._owner = owner

    async def get_by_code(self, **kwargs: Any) -> TimeSeriesFrame:
        return await _get_by_code_async(owner=self._owner, **kwargs)

    async def get_by_layer(self, **kwargs: Any) -> TimeSeriesFrame:
        return await _get_by_layer_async(owner=self._owner, **kwargs)


async def _run_data_service_async(awaitable: Any) -> TimeSeriesFrame:
    return await awaitable


async def _get_by_code_async(owner: AsyncDataService, **kwargs: Any) -> TimeSeriesFrame:
    service = _AsyncDataWorker(owner)
    return await service.get_by_code(**kwargs)


async def _get_by_layer_async(owner: AsyncDataService, **kwargs: Any) -> TimeSeriesFrame:
    service = _AsyncDataWorker(owner)
    return await service.get_by_layer(**kwargs)


class _AsyncDataWorker:
    """AsyncDataService実処理。"""

    def __init__(self, owner: AsyncDataService) -> None:
        self._owner = owner

    async def get_by_code(self, **kwargs: Any) -> TimeSeriesFrame:
        # 実装の一貫性のため、同期版ロジックを非同期トランスポートで再構成する。
        return await _get_by_code_async_impl(self._owner, **kwargs)

    async def get_by_layer(self, **kwargs: Any) -> TimeSeriesFrame:
        return await _get_by_layer_async_impl(self._owner, **kwargs)


async def _get_by_code_async_impl(owner: AsyncDataService, **kwargs: Any) -> TimeSeriesFrame:
    # 同期版の仕様を保つため、主要ロジックは共通関数に寄せる。
    sync_like = _DataAsyncLogic(owner)
    return await sync_like.get_by_code(**kwargs)


async def _get_by_layer_async_impl(owner: AsyncDataService, **kwargs: Any) -> TimeSeriesFrame:
    sync_like = _DataAsyncLogic(owner)
    return await sync_like.get_by_layer(**kwargs)


class _DataAsyncLogic:
    """非同期版の本体ロジック。"""

    def __init__(self, owner: AsyncDataService) -> None:
        self._owner = owner

    async def get_by_code(self, **kwargs: Any) -> TimeSeriesFrame:
        # 同期版DataServiceの処理を最小限で再実装。
        db = kwargs["db"]
        code = kwargs["code"]
        start = kwargs.get("start")
        end = kwargs.get("end")
        start_position = kwargs.get("start_position")
        lang = kwargs.get("lang")
        format = kwargs.get("format")
        strict_api = kwargs.get("strict_api")
        auto_split_codes = kwargs.get("auto_split_codes")
        raw_params = kwargs.get("raw_params")
        resume_token = kwargs.get("resume_token")
        output_order = kwargs.get("output_order")

        strict_mode = self._owner._config.strict_api if strict_api is None else strict_api
        split_mode = (
            self._owner._config.auto_split_codes if auto_split_codes is None else auto_split_codes
        )
        validate_strict_auto_split(strict_api=strict_mode, auto_split_codes=split_mode)

        lang_norm = normalize_lang(lang or self._owner._config.lang)
        format_norm = normalize_format(format or self._owner._config.format)
        db_norm = normalize_db(db)
        codes = normalize_codes(code)
        raw = normalize_raw_params(
            dict(raw_params) if raw_params is not None else None,
            allow_raw_override=self._owner._config.allow_raw_override,
        )
        start_norm, end_norm = normalize_code_periods(start=start, end=end)

        chunks = [codes] if strict_mode or not split_mode else split_codes_by_frequency_and_size(codes)
        code_order_map = {item: idx for idx, item in enumerate(codes)}
        endpoint = "/getDataCode"
        output_order_norm = (
            output_order
            if isinstance(output_order, OutputOrder)
            else OutputOrder(output_order or self._owner._config.output_order)
        )

        fingerprint = build_request_fingerprint(
            {
                "api_origin": self._owner._config.base_url,
                "endpoint": endpoint,
                "db": db_norm,
                "code": codes,
                "start": start_norm,
                "end": end_norm,
                "strict_api": strict_mode,
                "auto_split_codes": split_mode,
                "lang": lang_norm.value,
                "format": format_norm.value,
                "parser_version": PARSER_VERSION,
                "normalizer_version": NORMALIZER_VERSION,
                "schema_version": SCHEMA_VERSION,
                "output_order": output_order_norm.value,
                "raw_params": canonical_params(raw),
            }
        )

        start_chunk_index = 0
        chunk_start_position = start_position or 1
        if resume_token:
            token_state = decode_resume_token(resume_token)
            validate_resume_token(
                token_state,
                request_fingerprint=fingerprint,
                chunk_index=token_state.chunk_index,
                parser_version=PARSER_VERSION,
                normalizer_version=NORMALIZER_VERSION,
            )
            start_chunk_index = token_state.chunk_index
            chunk_start_position = token_state.next_position
            code_order_map = token_state.code_order_map

        cache_key = (
            f"api=code|origin={self._owner._config.base_url}|lang={lang_norm.value}|format={format_norm.value}|"
            f"parser={PARSER_VERSION}|normalizer={NORMALIZER_VERSION}|schema={SCHEMA_VERSION}|"
            f"strict_api={self._owner._config.strict_api}|auto_split={self._owner._config.auto_split_codes}|"
            f"consistency={self._owner._config.consistency_mode.value}|"
            f"conflict={self._owner._config.conflict_resolution.value}|"
            f"output_order={self._owner._config.output_order.value}|fp={fingerprint}"
        )
        cache_hit = self._owner._cache.get(key=cache_key, mode=self._owner._config.cache.mode)
        if cache_hit and not cache_hit.stale:
            return TimeSeriesFrame.from_cache_payload(cache_hit.payload["payload"])  # type: ignore[arg-type]

        dedupe: dict[tuple[str, str], TimeSeriesRecord] = {}
        last_meta: ResponseMeta | None = None
        conflicts_sample: list[dict[str, Any]] = []
        conflicts_count = 0

        for chunk_index, chunk in enumerate(chunks):
            if chunk_index < start_chunk_index:
                continue
            pager = CodePagerState(
                chunk_index=chunk_index,
                start_position=chunk_start_position if chunk_index == start_chunk_index else 1,
            )
            page_index = 0
            while True:
                params = {
                    "DB": db_norm,
                    "CODE": ",".join(chunk),
                    "LANG": lang_norm.value,
                    "FORMAT": format_norm.value,
                }
                if pager.start_position > 1:
                    params["STARTPOSITION"] = str(pager.start_position)
                if start_norm:
                    params["STARTDATE"] = start_norm
                if end_norm:
                    params["ENDDATE"] = end_norm
                params.update(raw)

                parsed, request_url, _ = await perform_async_request(
                    client=self._owner._client,
                    endpoint=endpoint,
                    params=params,
                    lang=lang_norm,
                    format=format_norm,
                    retry_config=self._owner._retry_config,
                    limiter=self._owner._limiter,
                    user_agent=self._owner._config.user_agent,
                    capture_full_response=self._owner._config.capture_full_response,
                )
                records = expand_timeseries_rows(
                    parsed.rows,
                    source_page_index=page_index,
                    code_order_map=code_order_map,
                )
                for record in records:
                    key = (record.series_code, record.survey_date)
                    existing = dedupe.get(key)
                    if existing is None:
                        dedupe[key] = record
                        continue
                    if existing.last_update != record.last_update:
                        conflicts_count += 1
                        conflicts_sample.append(
                            {
                                "series_code": record.series_code,
                                "survey_date": record.survey_date,
                                "existing_last_update": existing.last_update,
                                "incoming_last_update": record.last_update,
                            }
                        )
                        if self._owner._config.consistency_mode == ConsistencyMode.STRICT:
                            raise BojConsistencyError(
                                signal="last_update_conflict",
                                details=conflicts_sample[-1],
                            )
                    dedupe[key] = _choose_record(existing, record)

                next_position = parsed.next_position
                current_resume = create_resume_token(
                    api="code",
                    api_origin=self._owner._config.base_url,
                    request_fingerprint=fingerprint,
                    chunk_index=chunk_index,
                    next_position=next_position or 1,
                    lang=lang_norm.value,
                    format=format_norm.value,
                    parser_version=PARSER_VERSION,
                    normalizer_version=NORMALIZER_VERSION,
                    schema_version=SCHEMA_VERSION,
                    code_order_map=code_order_map,
                )
                last_meta = ResponseMeta(
                    status=parsed.status,
                    message_id=parsed.message_id,
                    message=parsed.message,
                    date_raw=parsed.date_raw,
                    date_parsed=parsed.date_parsed,
                    date_parse_warning=parsed.date_parse_warning,
                    date_semantics="output_file_created_at",
                    next_position=parsed.next_position,
                    parameters=parsed.parameters,
                    request_url=request_url,
                    schema_version=SCHEMA_VERSION,
                    parser_version=PARSER_VERSION,
                    normalizer_version=NORMALIZER_VERSION,
                    resume_token=current_resume,
                    conflicts_count=conflicts_count,
                    conflicts_sample=conflicts_sample[:20],
                )
                page_index += 1
                if not advance_code_position(state=pager, next_position=next_position):
                    break

        records_sorted = _sort_records(list(dedupe.values()), output_order=output_order_norm)
        meta = last_meta or _empty_meta(request_url="")
        if meta.next_position is None:
            meta.resume_token = None
        frame = TimeSeriesFrame(records=records_sorted, meta=meta)
        self._owner._cache.put(key=cache_key, payload=frame.to_cache_payload(), complete=True)
        return frame

    async def get_by_layer(self, **kwargs: Any) -> TimeSeriesFrame:
        db = kwargs["db"]
        frequency = kwargs["frequency"]
        layer = kwargs["layer"]
        start = kwargs.get("start")
        end = kwargs.get("end")
        start_position = kwargs.get("start_position")
        lang = kwargs.get("lang")
        format = kwargs.get("format")
        auto_paginate = kwargs.get("auto_paginate", True)
        raw_params = kwargs.get("raw_params")
        resume_token = kwargs.get("resume_token")
        resolve_wildcard = kwargs.get("resolve_wildcard")

        lang_norm = normalize_lang(lang or self._owner._config.lang)
        format_norm = normalize_format(format or self._owner._config.format)
        db_norm = normalize_db(db)
        freq_norm = normalize_frequency(frequency, required=True)
        assert freq_norm is not None
        layer_norm = normalize_layer(layer)
        start_norm, end_norm = normalize_periods(start=start, end=end, frequency=freq_norm)
        raw = normalize_raw_params(
            dict(raw_params) if raw_params is not None else None,
            allow_raw_override=self._owner._config.allow_raw_override,
        )

        needs_resolve = (
            self._owner._metadata_service is not None
            and _should_resolve_wildcard(
                config=self._owner._config,
                resolve_wildcard=resolve_wildcard,
                layer_norm=layer_norm,
                auto_paginate=auto_paginate,
                resume_token=resume_token,
                start_position=start_position,
            )
        )

        endpoint = "/getDataLayer"
        fingerprint = build_request_fingerprint(
            {
                "api_origin": self._owner._config.base_url,
                "endpoint": endpoint,
                "db": db_norm,
                "layer": layer_norm,
                "frequency": freq_norm.value,
                "start": start_norm,
                "end": end_norm,
                "lang": lang_norm.value,
                "format": format_norm.value,
                "consistency_mode": self._owner._config.consistency_mode.value,
                "conflict_resolution": self._owner._config.conflict_resolution.value,
                "parser_version": PARSER_VERSION,
                "normalizer_version": NORMALIZER_VERSION,
                "schema_version": SCHEMA_VERSION,
                "raw_params": canonical_params(raw),
            }
        )

        resolve_mode = (
            self._owner._config.resolve_wildcard if resolve_wildcard is None else resolve_wildcard
        )
        _rw_part = f"|resolve_wildcard={resolve_mode}" if resolve_mode is not None else ""
        cache_key = (
            f"api=layer|origin={self._owner._config.base_url}|lang={lang_norm.value}|format={format_norm.value}|"
            f"parser={PARSER_VERSION}|normalizer={NORMALIZER_VERSION}|schema={SCHEMA_VERSION}|"
            f"strict_api={self._owner._config.strict_api}|auto_split={self._owner._config.auto_split_codes}|"
            f"consistency={self._owner._config.consistency_mode.value}|"
            f"conflict={self._owner._config.conflict_resolution.value}|"
            f"output_order={self._owner._config.output_order.value}"
            f"{_rw_part}|fp={fingerprint}"
        )
        cache_hit = self._owner._cache.get(key=cache_key, mode=self._owner._config.cache.mode)
        if cache_hit and not cache_hit.stale:
            return TimeSeriesFrame.from_cache_payload(cache_hit.payload["payload"])  # type: ignore[arg-type]

        if needs_resolve:
            result = await self._get_by_layer_via_codes(
                db=db_norm, frequency=freq_norm,
                start=start_norm, end=end_norm,
                lang=lang_norm, format=format_norm,
                raw=raw, cache_key=cache_key,
            )
            if result is not None:
                return result

        pager = LayerPagerState(start_position=start_position or 1)
        if resume_token:
            token_state = decode_resume_token(resume_token)
            validate_resume_token(
                token_state,
                request_fingerprint=fingerprint,
                chunk_index=0,
                parser_version=PARSER_VERSION,
                normalizer_version=NORMALIZER_VERSION,
            )
            pager.start_position = token_state.next_position

        dedupe: dict[tuple[str, str], TimeSeriesRecord] = {}
        conflicts_count = 0
        conflicts_sample: list[dict[str, Any]] = []
        window_signal: str | None = None
        first_fetch = datetime.now(tz=_JST)
        page_index = 0
        last_meta: ResponseMeta | None = None
        code_order_map: dict[str, int] = {}

        while True:
            params: dict[str, str] = {
                "DB": db_norm,
                "FREQUENCY": freq_norm.value,
                "LANG": lang_norm.value,
                "FORMAT": format_norm.value,
                "LAYER": ",".join(layer_norm),
            }
            if pager.start_position > 1:
                params["STARTPOSITION"] = str(pager.start_position)
            if start_norm:
                params["STARTDATE"] = start_norm
            if end_norm:
                params["ENDDATE"] = end_norm
            params.update(raw)

            parsed, request_url, _ = await perform_async_request(
                client=self._owner._client,
                endpoint=endpoint,
                params=params,
                lang=lang_norm,
                format=format_norm,
                retry_config=self._owner._retry_config,
                limiter=self._owner._limiter,
                user_agent=self._owner._config.user_agent,
                capture_full_response=self._owner._config.capture_full_response,
            )

            now = datetime.now(tz=_JST)
            if _window_crossed(first_fetch=first_fetch, current=now):
                window_signal = "window_crossed"
                if self._owner._config.consistency_mode == ConsistencyMode.STRICT:
                    raise BojConsistencyError(
                        signal="window_crossed",
                        details={"first_fetch": first_fetch.isoformat(), "current": now.isoformat()},
                    )

            records = expand_timeseries_rows(
                parsed.rows,
                source_page_index=page_index,
                code_order_map=code_order_map,
            )
            for record in records:
                if record.series_code not in code_order_map:
                    code_order_map[record.series_code] = len(code_order_map)
                    record.original_code_index = code_order_map[record.series_code]
                key = (record.series_code, record.survey_date)
                existing = dedupe.get(key)
                if existing is None:
                    dedupe[key] = record
                    continue
                if existing.last_update != record.last_update:
                    conflicts_count += 1
                    detail = {
                        "series_code": record.series_code,
                        "survey_date": record.survey_date,
                        "existing_last_update": existing.last_update,
                        "incoming_last_update": record.last_update,
                    }
                    conflicts_sample.append(detail)
                    if self._owner._config.consistency_mode == ConsistencyMode.STRICT:
                        raise BojConsistencyError(signal="last_update_conflict", details=detail)
                dedupe[key] = _choose_record(existing, record)

            current_resume = create_resume_token(
                api="layer",
                api_origin=self._owner._config.base_url,
                request_fingerprint=fingerprint,
                chunk_index=0,
                next_position=parsed.next_position or 1,
                lang=lang_norm.value,
                format=format_norm.value,
                parser_version=PARSER_VERSION,
                normalizer_version=NORMALIZER_VERSION,
                schema_version=SCHEMA_VERSION,
                code_order_map=code_order_map,
            )
            last_meta = ResponseMeta(
                status=parsed.status,
                message_id=parsed.message_id,
                message=parsed.message,
                date_raw=parsed.date_raw,
                date_parsed=parsed.date_parsed,
                date_parse_warning=parsed.date_parse_warning,
                date_semantics="output_file_created_at",
                next_position=parsed.next_position,
                parameters=parsed.parameters,
                request_url=request_url,
                schema_version=SCHEMA_VERSION,
                parser_version=PARSER_VERSION,
                normalizer_version=NORMALIZER_VERSION,
                resume_token=current_resume,
                consistency_signal=window_signal,
                conflicts_count=conflicts_count,
                conflicts_sample=conflicts_sample[:20],
            )
            page_index += 1

            if not auto_paginate:
                break
            if not advance_layer_position(state=pager, next_position=parsed.next_position):
                break

        records_sorted = _sort_records(list(dedupe.values()), output_order=self._owner._config.output_order)
        meta = last_meta or _empty_meta(request_url="")
        if meta.next_position is None:
            meta.resume_token = None
        frame = TimeSeriesFrame(records=records_sorted, meta=meta)
        self._owner._cache.put(key=cache_key, payload=frame.to_cache_payload(), complete=True)
        return frame

    async def _get_by_layer_via_codes(
        self,
        *,
        db: str,
        frequency: Frequency,
        start: str | None,
        end: str | None,
        lang: Lang,
        format: Format,
        raw: dict[str, str],
        cache_key: str,
    ) -> TimeSeriesFrame | None:
        """非同期版の階層ワイルドカード→コードAPI委譲。詳細は同期版docstring参照。"""
        resolve_url = f"bojstat://resolve-wildcard/{db}?layer=*&frequency={frequency.value}"
        first_fetch = datetime.now(tz=_JST)

        try:
            meta_frame = await self._owner._metadata_service.get(db=db, lang=Lang.JP)
        except Exception:
            warnings.warn(
                f"メタデータ取得に失敗したため Layer API に直接アクセスします: db={db}",
                stacklevel=2,
            )
            return None

        codes = _resolve_codes_from_metadata(meta_frame, frequency)
        if not codes:
            empty = TimeSeriesFrame(
                records=[],
                meta=_empty_meta(request_url=resolve_url),
            )
            self._owner._cache.put(key=cache_key, payload=empty.to_cache_payload(), complete=True)
            return empty

        pre_code = datetime.now(tz=_JST)
        if _window_crossed(first_fetch=first_fetch, current=pre_code):
            if self._owner._config.consistency_mode == ConsistencyMode.STRICT:
                raise BojConsistencyError(
                    signal="window_crossed",
                    details={
                        "first_fetch": first_fetch.isoformat(),
                        "current": pre_code.isoformat(),
                    },
                )

        frame = await self.get_by_code(
            db=db, code=codes,
            start=start, end=end,
            lang=lang, format=format,
            strict_api=False,
            auto_split_codes=True,
            raw_params=raw if raw else None,
        )

        now = datetime.now(tz=_JST)
        if _window_crossed(first_fetch=first_fetch, current=now):
            if self._owner._config.consistency_mode == ConsistencyMode.STRICT:
                raise BojConsistencyError(
                    signal="window_crossed",
                    details={
                        "first_fetch": first_fetch.isoformat(),
                        "current": now.isoformat(),
                    },
                )
            if frame.meta:
                frame.meta.consistency_signal = "window_crossed"

        if frame.meta:
            frame.meta.request_url = resolve_url

        self._owner._cache.put(key=cache_key, payload=frame.to_cache_payload(), complete=True)
        return frame


def _choose_record(a: TimeSeriesRecord, b: TimeSeriesRecord) -> TimeSeriesRecord:
    if a.last_update is None:
        return b
    if b.last_update is None:
        return a
    if b.last_update > a.last_update:
        return b
    if b.last_update < a.last_update:
        return a
    a_rank = (a.source_page_index, a.source_row_index)
    b_rank = (b.source_page_index, b.source_row_index)
    return a if a_rank <= b_rank else b


def _sort_records(
    records: list[TimeSeriesRecord],
    *,
    output_order: OutputOrder,
) -> list[TimeSeriesRecord]:
    if output_order != OutputOrder.CANONICAL:
        return records

    def key_fn(record: TimeSeriesRecord) -> tuple[int, str, str, str]:
        order = record.original_code_index if record.original_code_index is not None else 10**9
        return (order, record.series_code, record.survey_date, record.last_update or "")

    return sorted(records, key=key_fn)


def _window_crossed(*, first_fetch: datetime, current: datetime) -> bool:
    def in_window(value: datetime) -> bool:
        minute = value.hour * 60 + value.minute
        begin = 8 * 60 + 50
        end = begin + 90
        return begin <= minute <= end

    return (not in_window(first_fetch)) and in_window(current)


def _empty_meta(*, request_url: str) -> ResponseMeta:
    return ResponseMeta(
        status=200,
        message_id="M181030I",
        message="正常に終了しましたが、該当データはありませんでした。",
        date_raw=None,
        date_parsed=None,
        date_parse_warning=None,
        date_semantics="output_file_created_at",
        next_position=None,
        parameters={},
        request_url=request_url,
        schema_version=SCHEMA_VERSION,
        parser_version=PARSER_VERSION,
        normalizer_version=NORMALIZER_VERSION,
    )
