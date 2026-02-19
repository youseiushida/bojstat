import httpx
from bojstat.cache import FileCache as FileCache
from bojstat.config import ClientConfig as ClientConfig, NORMALIZER_VERSION as NORMALIZER_VERSION, PARSER_VERSION as PARSER_VERSION, RetryConfig as RetryConfig, SCHEMA_VERSION as SCHEMA_VERSION
from bojstat.enums import Format as Format, Lang as Lang
from bojstat.errors import BojDateParseError as BojDateParseError
from bojstat.models import MetadataFrame as MetadataFrame
from bojstat.normalize import normalize_metadata_rows as normalize_metadata_rows
from bojstat.resume import build_request_fingerprint as build_request_fingerprint
from bojstat.services._transport import perform_async_request as perform_async_request, perform_sync_request as perform_sync_request
from bojstat.types import ResponseMeta as ResponseMeta
from bojstat.validation import normalize_db as normalize_db, normalize_format as normalize_format, normalize_lang as normalize_lang, normalize_raw_params as normalize_raw_params
from typing import Any

class MetadataService:
    """同期メタデータ取得サービス。"""
    def __init__(self, *, client: httpx.Client, config: ClientConfig, retry_config: RetryConfig, cache: FileCache, limiter: Any) -> None: ...
    def get(self, *, db: str, lang: Lang | str | None = None, format: Format | str | None = None, raw_params: dict[str, str] | None = None) -> MetadataFrame:
        """メタデータAPIで取得する。"""

class AsyncMetadataService:
    """非同期メタデータ取得サービス。"""
    def __init__(self, *, client: httpx.AsyncClient, config: ClientConfig, retry_config: RetryConfig, cache: FileCache, limiter: Any) -> None: ...
    async def get(self, *, db: str, lang: Lang | str | None = None, format: Format | str | None = None, raw_params: dict[str, str] | None = None) -> MetadataFrame:
        """メタデータAPIで取得する。"""
