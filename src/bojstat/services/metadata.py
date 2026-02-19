"""メタデータAPIサービス。"""

from __future__ import annotations

from typing import Any

import httpx

from bojstat.cache import FileCache
from bojstat.config import NORMALIZER_VERSION, PARSER_VERSION, SCHEMA_VERSION, ClientConfig, RetryConfig
from bojstat.enums import Format, Lang
from bojstat.errors import BojDateParseError
from bojstat.models import MetadataFrame
from bojstat.normalize import normalize_metadata_rows
from bojstat.resume import build_request_fingerprint
from bojstat.services._transport import perform_async_request, perform_sync_request
from bojstat.types import ResponseMeta
from bojstat.validation import normalize_db, normalize_format, normalize_lang, normalize_raw_params


class MetadataService:
    """同期メタデータ取得サービス。"""

    def __init__(
        self,
        *,
        client: httpx.Client,
        config: ClientConfig,
        retry_config: RetryConfig,
        cache: FileCache,
        limiter: Any,
    ) -> None:
        self._client = client
        self._config = config
        self._retry_config = retry_config
        self._cache = cache
        self._limiter = limiter

    def get(
        self,
        *,
        db: str,
        lang: Lang | str | None = None,
        format: Format | str | None = None,
        raw_params: dict[str, str] | None = None,
    ) -> MetadataFrame:
        """メタデータAPIで取得する。"""

        db_norm = normalize_db(db)
        lang_norm = normalize_lang(lang or self._config.lang)
        format_norm = normalize_format(format or self._config.format)
        raw = normalize_raw_params(
            raw_params,
            allow_raw_override=self._config.allow_raw_override,
        )
        endpoint = "/getMetadata"

        fingerprint = build_request_fingerprint(
            {
                "api_origin": self._config.base_url,
                "endpoint": endpoint,
                "db": db_norm,
                "lang": lang_norm.value,
                "format": format_norm.value,
                "parser_version": PARSER_VERSION,
                "normalizer_version": NORMALIZER_VERSION,
                "schema_version": SCHEMA_VERSION,
                "raw_params": sorted(raw.items()),
            }
        )
        cache_key = (
            f"api=metadata|origin={self._config.base_url}|lang={lang_norm.value}|"
            f"format={format_norm.value}|parser={PARSER_VERSION}|"
            f"normalizer={NORMALIZER_VERSION}|schema={SCHEMA_VERSION}|fp={fingerprint}"
        )

        cache_hit = self._cache.get(key=cache_key, mode=self._config.cache.mode)
        if cache_hit and not cache_hit.stale:
            return MetadataFrame.from_cache_payload(cache_hit.payload["payload"])  # type: ignore[arg-type]

        params = {
            "DB": db_norm,
            "LANG": lang_norm.value,
            "FORMAT": format_norm.value,
        }
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

        records = normalize_metadata_rows(parsed.rows)
        parameters = dict(parsed.parameters)
        if parsed.db is not None and "DB" not in parameters:
            parameters["DB"] = parsed.db
        meta = ResponseMeta(
            status=parsed.status,
            message_id=parsed.message_id,
            message=parsed.message,
            date_raw=parsed.date_raw,
            date_parsed=parsed.date_parsed,
            date_parse_warning=parsed.date_parse_warning,
            date_semantics="system_data_created_at",
            next_position=None,
            parameters=parameters,
            request_url=request_url,
            schema_version=SCHEMA_VERSION,
            parser_version=PARSER_VERSION,
            normalizer_version=NORMALIZER_VERSION,
        )
        frame = MetadataFrame(records=records, meta=meta)
        self._cache.put(key=cache_key, payload=frame.to_cache_payload(), complete=True)
        return frame


class AsyncMetadataService:
    """非同期メタデータ取得サービス。"""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        config: ClientConfig,
        retry_config: RetryConfig,
        cache: FileCache,
        limiter: Any,
    ) -> None:
        self._client = client
        self._config = config
        self._retry_config = retry_config
        self._cache = cache
        self._limiter = limiter

    async def get(
        self,
        *,
        db: str,
        lang: Lang | str | None = None,
        format: Format | str | None = None,
        raw_params: dict[str, str] | None = None,
    ) -> MetadataFrame:
        """メタデータAPIで取得する。"""

        db_norm = normalize_db(db)
        lang_norm = normalize_lang(lang or self._config.lang)
        format_norm = normalize_format(format or self._config.format)
        raw = normalize_raw_params(
            raw_params,
            allow_raw_override=self._config.allow_raw_override,
        )
        endpoint = "/getMetadata"

        fingerprint = build_request_fingerprint(
            {
                "api_origin": self._config.base_url,
                "endpoint": endpoint,
                "db": db_norm,
                "lang": lang_norm.value,
                "format": format_norm.value,
                "parser_version": PARSER_VERSION,
                "normalizer_version": NORMALIZER_VERSION,
                "schema_version": SCHEMA_VERSION,
                "raw_params": sorted(raw.items()),
            }
        )
        cache_key = (
            f"api=metadata|origin={self._config.base_url}|lang={lang_norm.value}|"
            f"format={format_norm.value}|parser={PARSER_VERSION}|"
            f"normalizer={NORMALIZER_VERSION}|schema={SCHEMA_VERSION}|fp={fingerprint}"
        )

        cache_hit = self._cache.get(key=cache_key, mode=self._config.cache.mode)
        if cache_hit and not cache_hit.stale:
            return MetadataFrame.from_cache_payload(cache_hit.payload["payload"])  # type: ignore[arg-type]

        params = {
            "DB": db_norm,
            "LANG": lang_norm.value,
            "FORMAT": format_norm.value,
        }
        params.update(raw)

        parsed, request_url, _ = await perform_async_request(
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

        records = normalize_metadata_rows(parsed.rows)
        parameters = dict(parsed.parameters)
        if parsed.db is not None and "DB" not in parameters:
            parameters["DB"] = parsed.db
        meta = ResponseMeta(
            status=parsed.status,
            message_id=parsed.message_id,
            message=parsed.message,
            date_raw=parsed.date_raw,
            date_parsed=parsed.date_parsed,
            date_parse_warning=parsed.date_parse_warning,
            date_semantics="system_data_created_at",
            next_position=None,
            parameters=parameters,
            request_url=request_url,
            schema_version=SCHEMA_VERSION,
            parser_version=PARSER_VERSION,
            normalizer_version=NORMALIZER_VERSION,
        )
        frame = MetadataFrame(records=records, meta=meta)
        self._cache.put(key=cache_key, payload=frame.to_cache_payload(), complete=True)
        return frame
