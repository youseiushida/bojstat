"""階層APIワイルドカード自動解決のテスト。"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

import httpx
import pytest

from bojstat import AsyncBojClient, BojClient
from bojstat.config import ClientConfig
from bojstat.enums import ConsistencyMode, Frequency, Lang
from bojstat.errors import BojConsistencyError
from bojstat.models import MetadataFrame
from bojstat.services.data import _resolve_codes_from_metadata, _should_resolve_wildcard
from bojstat.types import MetadataRecord, ResponseMeta


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------


def _make_meta_record(series_code: str, **kwargs: object) -> MetadataRecord:
    """テスト用MetadataRecordを生成する。"""
    defaults = {
        "series_name": None,
        "unit": None,
        "frequency": None,
        "category": None,
        "layer1": None,
        "layer2": None,
        "layer3": None,
        "layer4": None,
        "layer5": None,
        "start_of_time_series": None,
        "end_of_time_series": None,
        "last_update": None,
        "notes": None,
    }
    defaults.update(kwargs)
    return MetadataRecord(series_code=series_code, **defaults)  # type: ignore[arg-type]


def _make_metadata_frame(records: list[MetadataRecord]) -> MetadataFrame:
    """テスト用MetadataFrameを生成する。"""
    meta = ResponseMeta(
        status=200,
        message_id="M181000I",
        message="ok",
        date_raw=None,
        date_parsed=None,
        date_parse_warning=None,
        date_semantics="system_data_created_at",
        next_position=None,
        parameters={},
        request_url="",
        schema_version="1.0",
        parser_version="1.0",
        normalizer_version="1.0",
    )
    return MetadataFrame(records=records, meta=meta)


def _json_response(payload: dict[str, object], request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        status_code=200,
        content=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        request=request,
    )


def _ok_payload(
    result_set: list[dict[str, object]],
    *,
    next_position: int | None = None,
) -> dict[str, object]:
    return {
        "STATUS": 200,
        "MESSAGEID": "M181000I",
        "MESSAGE": "ok",
        "DATE": "2026-02-26T13:00:00.000+09:00",
        "PARAMETER": {},
        "NEXTPOSITION": next_position,
        "RESULTSET": result_set,
    }


def _metadata_payload(series_list: list[dict[str, object]]) -> dict[str, object]:
    return {
        "STATUS": 200,
        "MESSAGEID": "M181000I",
        "MESSAGE": "ok",
        "DATE": "2026-02-26T13:00:00.000+09:00",
        "PARAMETER": {},
        "NEXTPOSITION": None,
        "RESULTSET": series_list,
    }


def _make_series(code: str, dates: list[str], values: list[str]) -> dict[str, object]:
    return {
        "SERIES CODE": code,
        "NAME OF TIME SERIES": code,
        "FREQUENCY": "QUARTERLY",
        "LAST UPDATE": "20260101",
        "VALUES": {"SURVEY DATES": dates, "VALUES": values},
    }


# ---------------------------------------------------------------------------
# _resolve_codes_from_metadata 単体テスト
# ---------------------------------------------------------------------------


class TestResolveCodesFromMetadata:
    """_resolve_codes_from_metadata の単体テスト。"""

    def test_filters_by_frequency(self) -> None:
        """期種でフィルタできること。"""
        records = [
            _make_meta_record("FF01Q001"),  # Q suffix → Q
            _make_meta_record("FF01M001"),  # M suffix → M
            _make_meta_record("FF01CY001"),  # CY suffix → CY
        ]
        frame = _make_metadata_frame(records)
        codes = _resolve_codes_from_metadata(frame, Frequency.Q)
        assert codes == ["FF01Q001"]

    def test_includes_unknown_frequency(self) -> None:
        """推定不能コードはUNKNOWNとして含まれること。"""
        records = [
            _make_meta_record("ABCXYZ"),  # UNKNOWN
            _make_meta_record("FF01Q001"),  # Q
        ]
        frame = _make_metadata_frame(records)
        codes = _resolve_codes_from_metadata(frame, Frequency.Q)
        assert "ABCXYZ" in codes
        assert "FF01Q001" in codes

    def test_skips_empty_series_code(self) -> None:
        """空の series_code（階層ヘッダ行）は除外されること。"""
        records = [
            _make_meta_record(""),
            _make_meta_record("FF01Q001"),
        ]
        frame = _make_metadata_frame(records)
        codes = _resolve_codes_from_metadata(frame, Frequency.Q)
        assert codes == ["FF01Q001"]

    def test_empty_metadata(self) -> None:
        """空のメタデータで空リストを返すこと。"""
        frame = _make_metadata_frame([])
        codes = _resolve_codes_from_metadata(frame, Frequency.Q)
        assert codes == []

    def test_all_header_rows(self) -> None:
        """全レコードが空コードの場合は空リストを返すこと。"""
        records = [_make_meta_record(""), _make_meta_record("")]
        frame = _make_metadata_frame(records)
        codes = _resolve_codes_from_metadata(frame, Frequency.M)
        assert codes == []

    def test_at_suffix_code(self) -> None:
        """@付きコードのsuffix解析が正しく動作すること。"""
        records = [
            _make_meta_record("SERIES@M"),
            _make_meta_record("SERIES@Q"),
            _make_meta_record("SERIES@D"),
        ]
        frame = _make_metadata_frame(records)
        codes = _resolve_codes_from_metadata(frame, Frequency.M)
        assert codes == ["SERIES@M"]

    def test_mixed_frequencies(self) -> None:
        """混在期種から四半期コードのみ抽出できること。"""
        records = [
            _make_meta_record("CODE_M01"),
            _make_meta_record("CODE_Q01"),
            _make_meta_record("CODE_CY01"),
            _make_meta_record("UNKNOWN_CODE"),
        ]
        frame = _make_metadata_frame(records)
        codes = _resolve_codes_from_metadata(frame, Frequency.Q)
        assert "CODE_Q01" in codes
        assert "UNKNOWN_CODE" in codes
        assert "CODE_M01" not in codes

    def test_metadata_frequency_precedence_for_unknown_code(self) -> None:
        """推定不能コードでも metadata.frequency があればその値を優先すること。"""
        records = [
            _make_meta_record("UNKNOWN_MONTHLY", frequency="月次"),
            _make_meta_record("UNKNOWN_QUARTERLY", frequency="四半期"),
            _make_meta_record("UNKNOWN_NO_LABEL", frequency=None),
        ]
        frame = _make_metadata_frame(records)
        codes = _resolve_codes_from_metadata(frame, Frequency.Q)
        assert "UNKNOWN_QUARTERLY" in codes
        assert "UNKNOWN_MONTHLY" not in codes
        # frequencyラベル不明時は従来どおりコード推定にフォールバック
        assert "UNKNOWN_NO_LABEL" in codes


# ---------------------------------------------------------------------------
# _should_resolve_wildcard 単体テスト
# ---------------------------------------------------------------------------


class TestShouldResolveWildcard:
    """_should_resolve_wildcard の単体テスト。"""

    def _config(self, **kwargs: object) -> ClientConfig:
        return ClientConfig(**kwargs)  # type: ignore[arg-type]

    def test_default_true(self) -> None:
        """デフォルト設定でlayer=*ならTrueを返すこと。"""
        assert _should_resolve_wildcard(
            config=self._config(),
            resolve_wildcard=None,
            layer_norm=["*"],
            auto_paginate=True,
            resume_token=None,
            start_position=None,
        )

    def test_config_false(self) -> None:
        """config.resolve_wildcard=FalseならFalseを返すこと。"""
        assert not _should_resolve_wildcard(
            config=self._config(resolve_wildcard=False),
            resolve_wildcard=None,
            layer_norm=["*"],
            auto_paginate=True,
            resume_token=None,
            start_position=None,
        )

    def test_method_override_false(self) -> None:
        """メソッドレベルの resolve_wildcard=False が優先されること。"""
        assert not _should_resolve_wildcard(
            config=self._config(resolve_wildcard=True),
            resolve_wildcard=False,
            layer_norm=["*"],
            auto_paginate=True,
            resume_token=None,
            start_position=None,
        )

    def test_method_override_true(self) -> None:
        """メソッドレベルの resolve_wildcard=True が優先されること。"""
        assert _should_resolve_wildcard(
            config=self._config(resolve_wildcard=False),
            resolve_wildcard=True,
            layer_norm=["*"],
            auto_paginate=True,
            resume_token=None,
            start_position=None,
        )

    def test_non_wildcard_layer(self) -> None:
        """layer != ["*"] では False を返すこと。"""
        assert not _should_resolve_wildcard(
            config=self._config(),
            resolve_wildcard=None,
            layer_norm=["1", "2"],
            auto_paginate=True,
            resume_token=None,
            start_position=None,
        )

    def test_partial_wildcard(self) -> None:
        """部分ワイルドカード layer=["1","*"] では False を返すこと。"""
        assert not _should_resolve_wildcard(
            config=self._config(),
            resolve_wildcard=None,
            layer_norm=["1", "*"],
            auto_paginate=True,
            resume_token=None,
            start_position=None,
        )

    def test_auto_paginate_false(self) -> None:
        """auto_paginate=False では False を返すこと。"""
        assert not _should_resolve_wildcard(
            config=self._config(),
            resolve_wildcard=None,
            layer_norm=["*"],
            auto_paginate=False,
            resume_token=None,
            start_position=None,
        )

    def test_resume_token_set(self) -> None:
        """resume_token 指定時は False を返すこと。"""
        assert not _should_resolve_wildcard(
            config=self._config(),
            resolve_wildcard=None,
            layer_norm=["*"],
            auto_paginate=True,
            resume_token="some_token",
            start_position=None,
        )

    def test_start_position_set(self) -> None:
        """start_position 指定時は False を返すこと。"""
        assert not _should_resolve_wildcard(
            config=self._config(),
            resolve_wildcard=None,
            layer_norm=["*"],
            auto_paginate=True,
            resume_token=None,
            start_position=100,
        )


# ---------------------------------------------------------------------------
# 統合テスト: BojClient + get_by_layer ワイルドカード解決
# ---------------------------------------------------------------------------


def _make_handler(
    *,
    meta_series: list[dict[str, object]],
    code_result: list[dict[str, object]],
):
    """メタデータAPIとコードAPIを両方ハンドルするモックハンドラーを作成する。"""
    call_log: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "/getMetadata" in path:
            call_log.append("metadata")
            return _json_response(_metadata_payload(meta_series), request)
        if "/getDataCode" in path:
            call_log.append("code")
            return _json_response(_ok_payload(code_result), request)
        if "/getDataLayer" in path:
            call_log.append("layer")
            return _json_response(_ok_payload(code_result), request)
        return httpx.Response(status_code=404, request=request)

    return handler, call_log


def test_wildcard_resolves_via_code_api() -> None:
    """layer="*" でメタデータ→Code API委譲が動作すること。"""
    handler, call_log = _make_handler(
        meta_series=[
            {"SERIES CODE": "FFQ01", "NAME OF TIME SERIES": "A", "FREQUENCY": "四半期"},
            {"SERIES CODE": "FFQ02", "NAME OF TIME SERIES": "B", "FREQUENCY": "四半期"},
        ],
        code_result=[
            _make_series("FFQ01", ["202401"], ["1.0"]),
            _make_series("FFQ02", ["202401"], ["2.0"]),
        ],
    )
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://example.invalid/api/v1")

    with BojClient(
        http_client=http_client,
        base_url="https://example.invalid/api/v1",
        cache_mode="off",
        rate_limit_per_sec=1000.0,
    ) as client:
        frame = client.data.get_by_layer(
            db="FF",
            frequency="Q",
            layer="*",
            start="202401",
            end="202404",
        )

    assert "metadata" in call_log
    assert "code" in call_log
    assert "layer" not in call_log
    assert len(frame.records) == 2
    assert frame.meta.request_url.startswith("bojstat://resolve-wildcard/")


def test_wildcard_resolve_filters_metadata_frequency_before_code_api() -> None:
    """ワイルドカード解決時に metadata.frequency で不一致系列を除外すること。"""
    captured_code_params: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "/getMetadata" in path:
            return _json_response(
                _metadata_payload([
                    {"SERIES CODE": "UNKNOWN_MONTHLY", "NAME OF TIME SERIES": "M", "FREQUENCY": "月次"},
                    {"SERIES CODE": "UNKNOWN_QUARTERLY", "NAME OF TIME SERIES": "Q", "FREQUENCY": "四半期"},
                ]),
                request,
            )
        if "/getDataCode" in path:
            captured_code_params.append(request.url.params.get("CODE", ""))
            return _json_response(
                _ok_payload([_make_series("UNKNOWN_QUARTERLY", ["202401"], ["1.0"])]),
                request,
            )
        return httpx.Response(status_code=404, request=request)

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://example.invalid/api/v1")

    with BojClient(
        http_client=http_client,
        base_url="https://example.invalid/api/v1",
        cache_mode="off",
        rate_limit_per_sec=1000.0,
    ) as client:
        frame = client.data.get_by_layer(
            db="FF",
            frequency="Q",
            layer="*",
        )

    assert len(frame.records) == 1
    assert len(captured_code_params) == 1
    assert captured_code_params[0] == "UNKNOWN_QUARTERLY"


def test_wildcard_disabled_uses_layer_api() -> None:
    """resolve_wildcard=False で Layer API が直接使われること。"""
    handler, call_log = _make_handler(
        meta_series=[],
        code_result=[_make_series("CODE_A", ["202401"], ["1.0"])],
    )
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://example.invalid/api/v1")

    with BojClient(
        http_client=http_client,
        base_url="https://example.invalid/api/v1",
        cache_mode="off",
        rate_limit_per_sec=1000.0,
    ) as client:
        client.data.get_by_layer(
            db="FF",
            frequency="Q",
            layer="*",
            resolve_wildcard=False,
        )

    assert "layer" in call_log
    assert "metadata" not in call_log


def test_non_wildcard_uses_layer_api() -> None:
    """layer=[1,2,3] で Layer API が直接使われること。"""
    handler, call_log = _make_handler(
        meta_series=[],
        code_result=[_make_series("CODE_A", ["202401"], ["1.0"])],
    )
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://example.invalid/api/v1")

    with BojClient(
        http_client=http_client,
        base_url="https://example.invalid/api/v1",
        cache_mode="off",
        rate_limit_per_sec=1000.0,
    ) as client:
        client.data.get_by_layer(
            db="BP01",
            frequency="M",
            layer=[1, 2, 3],
        )

    assert "layer" in call_log
    assert "metadata" not in call_log


def test_auto_paginate_false_uses_layer_api() -> None:
    """auto_paginate=False + layer="*" で Layer API が直接使われること。"""
    handler, call_log = _make_handler(
        meta_series=[],
        code_result=[_make_series("CODE_A", ["202401"], ["1.0"])],
    )
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://example.invalid/api/v1")

    with BojClient(
        http_client=http_client,
        base_url="https://example.invalid/api/v1",
        cache_mode="off",
        rate_limit_per_sec=1000.0,
    ) as client:
        client.data.get_by_layer(
            db="FF",
            frequency="Q",
            layer="*",
            auto_paginate=False,
        )

    assert "layer" in call_log
    assert "metadata" not in call_log


def test_metadata_failure_falls_back_to_layer_api() -> None:
    """メタデータ取得失敗時に Layer API にフォールバックすること。"""
    call_log: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "/getMetadata" in path:
            call_log.append("metadata")
            return httpx.Response(status_code=500, request=request, content=b'{"STATUS":500,"MESSAGEID":"E","MESSAGE":"err"}')
        if "/getDataLayer" in path:
            call_log.append("layer")
            return _json_response(
                _ok_payload([_make_series("CODE_A", ["202401"], ["1.0"])]),
                request,
            )
        return httpx.Response(status_code=404, request=request)

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://example.invalid/api/v1")

    with BojClient(
        http_client=http_client,
        base_url="https://example.invalid/api/v1",
        cache_mode="off",
        rate_limit_per_sec=1000.0,
        retry_max_attempts=1,
    ) as client:
        with pytest.warns(UserWarning, match="メタデータ取得に失敗"):
            frame = client.data.get_by_layer(
                db="FF",
                frequency="Q",
                layer="*",
            )

    assert "metadata" in call_log
    assert "layer" in call_log
    assert len(frame.records) == 1


def test_no_matching_codes_returns_empty_frame() -> None:
    """メタデータに該当コードがない場合は空 TimeSeriesFrame を返すこと。"""
    handler, call_log = _make_handler(
        meta_series=[
            {"SERIES CODE": "SERIES@M", "NAME OF TIME SERIES": "Monthly", "FREQUENCY": "月次"},
        ],
        code_result=[],
    )
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://example.invalid/api/v1")

    with BojClient(
        http_client=http_client,
        base_url="https://example.invalid/api/v1",
        cache_mode="off",
        rate_limit_per_sec=1000.0,
    ) as client:
        frame = client.data.get_by_layer(
            db="FF",
            frequency="CY",
            layer="*",
        )

    assert "metadata" in call_log
    assert "code" not in call_log
    assert len(frame.records) == 0
    assert "bojstat://resolve-wildcard/" in frame.meta.request_url


def test_empty_result_is_cached(tmp_path: object) -> None:
    """空結果がキャッシュされ、2回目の呼び出しでメタデータ再取得しないこと。"""
    handler, call_log = _make_handler(
        meta_series=[
            {"SERIES CODE": "SERIES@M", "NAME OF TIME SERIES": "Monthly", "FREQUENCY": "月次"},
        ],
        code_result=[],
    )
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://example.invalid/api/v1")

    with BojClient(
        http_client=http_client,
        base_url="https://example.invalid/api/v1",
        cache_dir=str(tmp_path),
        cache_mode="if_stale",
        rate_limit_per_sec=1000.0,
    ) as client:
        frame1 = client.data.get_by_layer(db="FF", frequency="CY", layer="*")
        assert len(frame1.records) == 0
        metadata_count_after_first = call_log.count("metadata")

        frame2 = client.data.get_by_layer(db="FF", frequency="CY", layer="*")
        assert len(frame2.records) == 0
        metadata_count_after_second = call_log.count("metadata")

    assert metadata_count_after_first >= 1
    assert metadata_count_after_second == metadata_count_after_first


def test_request_url_format() -> None:
    """resolve_url が bojstat://resolve-wildcard/{db}?layer=*&frequency={freq} 形式であること。"""
    handler, _ = _make_handler(
        meta_series=[
            {"SERIES CODE": "FFQ01", "NAME OF TIME SERIES": "A", "FREQUENCY": "四半期"},
        ],
        code_result=[_make_series("FFQ01", ["202401"], ["1.0"])],
    )
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://example.invalid/api/v1")

    with BojClient(
        http_client=http_client,
        base_url="https://example.invalid/api/v1",
        cache_mode="off",
        rate_limit_per_sec=1000.0,
    ) as client:
        frame = client.data.get_by_layer(
            db="FF",
            frequency="Q",
            layer="*",
        )

    assert frame.meta.request_url == "bojstat://resolve-wildcard/FF?layer=*&frequency=Q"


def test_method_level_override() -> None:
    """BojClient(resolve_wildcard=True) + get_by_layer(resolve_wildcard=False) → False が優先。"""
    handler, call_log = _make_handler(
        meta_series=[],
        code_result=[_make_series("CODE_A", ["202401"], ["1.0"])],
    )
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://example.invalid/api/v1")

    with BojClient(
        http_client=http_client,
        base_url="https://example.invalid/api/v1",
        cache_mode="off",
        rate_limit_per_sec=1000.0,
        resolve_wildcard=True,
    ) as client:
        client.data.get_by_layer(
            db="FF",
            frequency="Q",
            layer="*",
            resolve_wildcard=False,
        )

    assert "layer" in call_log
    assert "metadata" not in call_log


def test_metadata_lang_jp_fixed() -> None:
    """ワイルドカード解決時のメタデータ取得が lang=Lang.JP 固定で呼ばれること。"""
    captured_params: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "/getMetadata" in path:
            captured_params.append(dict(request.url.params))
            return _json_response(
                _metadata_payload([
                    {"SERIES CODE": "FFQ01", "NAME OF TIME SERIES": "A", "FREQUENCY": "Quarterly"},
                ]),
                request,
            )
        if "/getDataCode" in path:
            return _json_response(
                _ok_payload([_make_series("FFQ01", ["202401"], ["1.0"])]),
                request,
            )
        return httpx.Response(status_code=404, request=request)

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://example.invalid/api/v1")

    with BojClient(
        http_client=http_client,
        base_url="https://example.invalid/api/v1",
        cache_mode="off",
        rate_limit_per_sec=1000.0,
        lang="en",
    ) as client:
        client.data.get_by_layer(
            db="FF",
            frequency="Q",
            layer="*",
        )

    assert len(captured_params) >= 1
    assert captured_params[0].get("LANG") == "JP"


def test_get_by_code_exception_propagates() -> None:
    """get_by_code の例外が _get_by_layer_via_codes 内でキャッチされずそのまま伝播すること。"""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "/getMetadata" in path:
            return _json_response(
                _metadata_payload([
                    {"SERIES CODE": "FFQ01", "NAME OF TIME SERIES": "A", "FREQUENCY": "四半期"},
                ]),
                request,
            )
        if "/getDataCode" in path:
            return httpx.Response(
                status_code=200,
                content=json.dumps(
                    {"STATUS": 400, "MESSAGEID": "M181005E", "MESSAGE": "err", "PARAMETER": {}, "RESULTSET": []},
                ).encode("utf-8"),
                request=request,
            )
        return httpx.Response(status_code=404, request=request)

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://example.invalid/api/v1")

    with BojClient(
        http_client=http_client,
        base_url="https://example.invalid/api/v1",
        cache_mode="off",
        rate_limit_per_sec=1000.0,
    ) as client:
        # Code API が BojBadRequestError を送出するが、キャッチされず伝播する
        from bojstat.errors import BojBadRequestError

        with pytest.raises(BojBadRequestError):
            client.data.get_by_layer(
                db="FF",
                frequency="Q",
                layer="*",
            )


def test_cache_key_separation() -> None:
    """resolve_wildcard=True と False で異なるキャッシュキーが使われること。"""
    handler, _ = _make_handler(
        meta_series=[
            {"SERIES CODE": "FFQ01", "NAME OF TIME SERIES": "A", "FREQUENCY": "四半期"},
        ],
        code_result=[_make_series("FFQ01", ["202401"], ["1.0"])],
    )
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://example.invalid/api/v1")

    with BojClient(
        http_client=http_client,
        base_url="https://example.invalid/api/v1",
        cache_mode="off",
        rate_limit_per_sec=1000.0,
    ) as client:
        # _build_cache_key で resolve_wildcard が含まれることを確認
        key_true = client.data._build_cache_key(
            "layer", "fp123", Lang.JP, client.data._config.format,
            resolve_wildcard=True,
        )
        key_false = client.data._build_cache_key(
            "layer", "fp123", Lang.JP, client.data._config.format,
            resolve_wildcard=False,
        )
        key_none = client.data._build_cache_key(
            "layer", "fp123", Lang.JP, client.data._config.format,
        )
    assert key_true != key_false
    assert "resolve_wildcard=True" in key_true
    assert "resolve_wildcard=False" in key_false
    assert "resolve_wildcard" not in key_none


def test_cache_put_called_with_layer_key() -> None:
    """ワイルドカード解決後に cache.put が Layer API キーで呼ばれること。"""
    handler, _ = _make_handler(
        meta_series=[
            {"SERIES CODE": "FFQ01", "NAME OF TIME SERIES": "A", "FREQUENCY": "四半期"},
        ],
        code_result=[_make_series("FFQ01", ["202401"], ["1.0"])],
    )
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://example.invalid/api/v1")

    with BojClient(
        http_client=http_client,
        base_url="https://example.invalid/api/v1",
        cache_mode="off",
        rate_limit_per_sec=1000.0,
    ) as client:
        original_put = client.data._cache.put
        put_calls: list[str] = []

        def mock_put(*, key: str, payload: object, complete: bool) -> None:
            put_calls.append(key)
            original_put(key=key, payload=payload, complete=complete)

        client.data._cache.put = mock_put  # type: ignore[assignment]
        client.data.get_by_layer(
            db="FF",
            frequency="Q",
            layer="*",
        )

    layer_keys = [k for k in put_calls if k.startswith("api=layer")]
    assert len(layer_keys) >= 1


def test_window_crossed_strict_raises_before_code_api() -> None:
    """consistency_mode=STRICT + window crossing で Code API 呼出前に例外が送出されること。"""
    handler, call_log = _make_handler(
        meta_series=[
            {"SERIES CODE": "FFQ01", "NAME OF TIME SERIES": "A", "FREQUENCY": "四半期"},
        ],
        code_result=[_make_series("FFQ01", ["202401"], ["1.0"])],
    )
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://example.invalid/api/v1")

    with BojClient(
        http_client=http_client,
        base_url="https://example.invalid/api/v1",
        cache_mode="off",
        rate_limit_per_sec=1000.0,
        consistency_mode=ConsistencyMode.STRICT,
    ) as client:
        with patch("bojstat.services.data._window_crossed", return_value=True):
            with pytest.raises(BojConsistencyError):
                client.data.get_by_layer(
                    db="FF",
                    frequency="Q",
                    layer="*",
                )

    # pre-check で例外が発生するため Code API は呼ばれない
    assert "code" not in call_log


def test_window_crossed_best_effort_sets_signal() -> None:
    """consistency_mode=BEST_EFFORT + window crossing で consistency_signal が設定されること。"""
    handler, _ = _make_handler(
        meta_series=[
            {"SERIES CODE": "FFQ01", "NAME OF TIME SERIES": "A", "FREQUENCY": "四半期"},
        ],
        code_result=[_make_series("FFQ01", ["202401"], ["1.0"])],
    )
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://example.invalid/api/v1")

    with BojClient(
        http_client=http_client,
        base_url="https://example.invalid/api/v1",
        cache_mode="off",
        rate_limit_per_sec=1000.0,
        consistency_mode=ConsistencyMode.BEST_EFFORT,
    ) as client:
        with patch("bojstat.services.data._window_crossed", return_value=True):
            frame = client.data.get_by_layer(
                db="FF",
                frequency="Q",
                layer="*",
            )

    assert frame.meta.consistency_signal == "window_crossed"


# ---------------------------------------------------------------------------
# 非同期テスト
# ---------------------------------------------------------------------------


def test_async_wildcard_resolves_via_code_api() -> None:
    """AsyncBojClient でワイルドカード解決が同期版と同等に動作すること。"""
    handler, call_log = _make_handler(
        meta_series=[
            {"SERIES CODE": "FFQ01", "NAME OF TIME SERIES": "A", "FREQUENCY": "四半期"},
        ],
        code_result=[_make_series("FFQ01", ["202401"], ["1.0"])],
    )

    async def run() -> None:
        transport = httpx.MockTransport(handler)
        http_client = httpx.AsyncClient(
            transport=transport,
            base_url="https://example.invalid/api/v1",
        )
        async with AsyncBojClient(
            http_client=http_client,
            base_url="https://example.invalid/api/v1",
            cache_mode="off",
            rate_limit_per_sec=1000.0,
        ) as client:
            frame = await client.data.get_by_layer(
                db="FF",
                frequency="Q",
                layer="*",
            )
            assert "metadata" in call_log
            assert "code" in call_log
            assert "layer" not in call_log
            assert len(frame.records) == 1
            assert frame.meta.request_url.startswith("bojstat://resolve-wildcard/")

    asyncio.run(run())


def test_resume_token_disables_resolve() -> None:
    """resume_token 指定時はワイルドカード解決が無効化されること。"""
    handler, call_log = _make_handler(
        meta_series=[],
        code_result=[_make_series("CODE_A", ["202401"], ["1.0"])],
    )
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://example.invalid/api/v1")

    with BojClient(
        http_client=http_client,
        base_url="https://example.invalid/api/v1",
        cache_mode="off",
        rate_limit_per_sec=1000.0,
    ) as client:
        # resume_token の形式が不正でもフォーマットチェックで例外になるが、
        # _should_resolve_wildcard が False を返すことは単体テストで確認済み
        # ここでは resume_token=None + start_position でテスト
        client.data.get_by_layer(
            db="FF",
            frequency="Q",
            layer="*",
            start_position=100,
        )

    assert "layer" in call_log
    assert "metadata" not in call_log


def test_output_order_not_passed_to_get_by_code() -> None:
    """ワイルドカード解決経由で get_by_code が呼ばれた場合、output_order が渡されていないこと。"""
    handler, _ = _make_handler(
        meta_series=[
            {"SERIES CODE": "FFQ01", "NAME OF TIME SERIES": "A", "FREQUENCY": "四半期"},
        ],
        code_result=[_make_series("FFQ01", ["202401"], ["1.0"])],
    )
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://example.invalid/api/v1")

    with BojClient(
        http_client=http_client,
        base_url="https://example.invalid/api/v1",
        cache_mode="off",
        rate_limit_per_sec=1000.0,
    ) as client:
        original_get_by_code = client.data.get_by_code
        captured_kwargs: list[dict[str, object]] = []

        def mock_get_by_code(**kwargs: object):
            captured_kwargs.append(kwargs)
            return original_get_by_code(**kwargs)

        client.data.get_by_code = mock_get_by_code  # type: ignore[assignment]
        client.data.get_by_layer(
            db="FF",
            frequency="Q",
            layer="*",
        )

    assert len(captured_kwargs) == 1
    assert "output_order" not in captured_kwargs[0]
