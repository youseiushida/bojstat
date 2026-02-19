import httpx
from bojstat.cache import FileCache as FileCache
from bojstat.config import ClientConfig as ClientConfig, NORMALIZER_VERSION as NORMALIZER_VERSION, PARSER_VERSION as PARSER_VERSION, RetryConfig as RetryConfig, SCHEMA_VERSION as SCHEMA_VERSION
from bojstat.enums import ConsistencyMode as ConsistencyMode, Format as Format, Lang as Lang, OutputOrder as OutputOrder
from bojstat.errors import BojConsistencyError as BojConsistencyError, BojDateParseError as BojDateParseError
from bojstat.models import TimeSeriesFrame as TimeSeriesFrame
from bojstat.normalize import expand_timeseries_rows as expand_timeseries_rows
from bojstat.pager.code_pager import CodePagerState as CodePagerState, advance_code_position as advance_code_position
from bojstat.pager.layer_pager import LayerPagerState as LayerPagerState, advance_layer_position as advance_layer_position
from bojstat.resume import build_request_fingerprint as build_request_fingerprint, create_resume_token as create_resume_token, decode_resume_token as decode_resume_token, validate_resume_token as validate_resume_token
from bojstat.services._transport import perform_async_request as perform_async_request, perform_sync_request as perform_sync_request
from bojstat.types import ResponseMeta as ResponseMeta, TimeSeriesRecord as TimeSeriesRecord
from bojstat.validation import canonical_params as canonical_params, normalize_code_periods as normalize_code_periods, normalize_codes as normalize_codes, normalize_format as normalize_format, normalize_frequency as normalize_frequency, normalize_lang as normalize_lang, normalize_layer as normalize_layer, normalize_periods as normalize_periods, normalize_raw_params as normalize_raw_params, split_codes_by_frequency_and_size as split_codes_by_frequency_and_size, validate_strict_auto_split as validate_strict_auto_split
from collections.abc import Mapping, Sequence
from typing import Any

class DataService:
    """同期データ取得サービス。"""
    def __init__(self, *, client: httpx.Client, config: ClientConfig, retry_config: RetryConfig, cache: FileCache, limiter: Any) -> None: ...
    def get_by_code(self, *, db: str, code: str | Sequence[str], start: str | None = None, end: str | None = None, start_position: int | None = None, lang: Lang | str | None = None, format: Format | str | None = None, strict_api: bool | None = None, auto_split_codes: bool | None = None, raw_params: Mapping[str, str] | None = None, resume_token: str | None = None, output_order: OutputOrder | str | None = None) -> TimeSeriesFrame:
        """コードAPIで時系列データを取得する。"""
    def get_by_layer(self, *, db: str, frequency: str, layer: str | Sequence[str | int], start: str | None = None, end: str | None = None, start_position: int | None = None, lang: Lang | str | None = None, format: Format | str | None = None, auto_paginate: bool = True, raw_params: Mapping[str, str] | None = None, resume_token: str | None = None) -> TimeSeriesFrame:
        """階層APIで時系列データを取得する。"""

class AsyncDataService:
    """非同期データ取得サービス。"""
    def __init__(self, *, client: httpx.AsyncClient, config: ClientConfig, retry_config: RetryConfig, cache: FileCache, limiter: Any) -> None: ...
    async def get_by_code(self, **kwargs: Any) -> TimeSeriesFrame:
        """同期実装互換の非同期版。"""
    async def get_by_layer(self, **kwargs: Any) -> TimeSeriesFrame:
        """同期実装互換の非同期版。"""

class _AsyncBridge:
    """同期ロジックを非同期トランスポートで再利用する橋渡し。"""
    def __init__(self, owner: AsyncDataService) -> None: ...
    async def get_by_code(self, **kwargs: Any) -> TimeSeriesFrame: ...
    async def get_by_layer(self, **kwargs: Any) -> TimeSeriesFrame: ...

class _AsyncDataWorker:
    """AsyncDataService実処理。"""
    def __init__(self, owner: AsyncDataService) -> None: ...
    async def get_by_code(self, **kwargs: Any) -> TimeSeriesFrame: ...
    async def get_by_layer(self, **kwargs: Any) -> TimeSeriesFrame: ...

class _DataAsyncLogic:
    """非同期版の本体ロジック。"""
    def __init__(self, owner: AsyncDataService) -> None: ...
    async def get_by_code(self, **kwargs: Any) -> TimeSeriesFrame: ...
    async def get_by_layer(self, **kwargs: Any) -> TimeSeriesFrame: ...
