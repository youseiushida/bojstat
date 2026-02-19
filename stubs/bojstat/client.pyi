import httpx
from _typeshed import Incomplete
from bojstat.cache import FileCache as FileCache
from bojstat.config import CacheConfig as CacheConfig, ClientConfig as ClientConfig, RetryConfig as RetryConfig
from bojstat.enums import CacheMode as CacheMode, ConflictResolution as ConflictResolution, ConsistencyMode as ConsistencyMode, Format as Format, Lang as Lang, OutputOrder as OutputOrder
from bojstat.errors_catalog import ErrorClassifier as ErrorClassifier
from bojstat.http import AsyncRateLimiter as AsyncRateLimiter, SyncRateLimiter as SyncRateLimiter
from bojstat.services.data import AsyncDataService as AsyncDataService, DataService as DataService
from bojstat.services.metadata import AsyncMetadataService as AsyncMetadataService, MetadataService as MetadataService
from bojstat.validation import normalize_format as normalize_format, normalize_lang as normalize_lang, validate_strict_auto_split as validate_strict_auto_split
from pathlib import Path
from typing import Any

class BojClient:
    """日本銀行APIの同期クライアント。"""
    data: Incomplete
    metadata: Incomplete
    errors: Incomplete
    def __init__(self, *, timeout: float = 30.0, base_url: str = 'https://www.stat-search.boj.or.jp/api/v1', lang: Lang | str = ..., format: Format | str = ..., user_agent: str = 'bojstat/0.1.0', rate_limit_per_sec: float = 1.0, cache_dir: str | Path | None = None, cache_mode: CacheMode | str = ..., cache_ttl: int = ..., strict_api: bool = True, auto_split_codes: bool = False, consistency_mode: ConsistencyMode | str = ..., conflict_resolution: ConflictResolution | str = ..., output_order: OutputOrder | str = ..., allow_raw_override: bool = False, metadata_freshness_strict: bool = False, capture_full_response: bool = False, retry_max_attempts: int = 5, retry_transport_max_attempts: int | None = None, retry_base_delay: float = 0.5, retry_cap_delay: float = 8.0, retry_jitter_ratio: float = 1.0, retry_on_403: bool = False, retry_on_403_max_attempts: int = 2, http_client: httpx.Client | None = None, http2: bool = False, proxy: str | None = None, limits: httpx.Limits | None = None) -> None:
        """クライアントを初期化する。

        Args:
            timeout: HTTPタイムアウト秒。
            base_url: APIベースURL。
            lang: 既定言語。
            format: 既定出力形式。
            user_agent: User-Agent。
            rate_limit_per_sec: 1秒あたり送信回数上限。
            cache_dir: キャッシュディレクトリ。
            cache_mode: キャッシュモード。
            cache_ttl: キャッシュTTL秒。
            strict_api: 仕様準拠モード。
            auto_split_codes: コード自動分割有効化。
            consistency_mode: 整合性モード。
            conflict_resolution: 競合解決ルール。
            output_order: 出力順序。
            allow_raw_override: raw_params上書き許可。
            metadata_freshness_strict: DATE解析失敗を例外化するか。
            capture_full_response: 例外に完全レスポンスを保持するか。
            retry_max_attempts: 最大再試行回数。
            retry_transport_max_attempts: 通信例外時の最大再試行回数。
            retry_base_delay: バックオフ基準秒。
            retry_cap_delay: バックオフ上限秒。
            retry_jitter_ratio: バックオフ待機のゆらぎ係数。
            retry_on_403: 403再試行有効化。
            retry_on_403_max_attempts: 403時最大再試行回数。
            http_client: 外部httpx.Client。
            http2: HTTP/2有効化。
            proxy: プロキシ。
            limits: httpx接続制御。
        """
    def close(self) -> None:
        """内部Clientをクローズする。"""
    def __enter__(self) -> BojClient:
        """コンテキスト開始。"""
    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        """コンテキスト終了。"""

class AsyncBojClient:
    """日本銀行APIの非同期クライアント。"""
    data: Incomplete
    metadata: Incomplete
    errors: Incomplete
    def __init__(self, *, timeout: float = 30.0, base_url: str = 'https://www.stat-search.boj.or.jp/api/v1', lang: Lang | str = ..., format: Format | str = ..., user_agent: str = 'bojstat/0.1.0', rate_limit_per_sec: float = 1.0, cache_dir: str | Path | None = None, cache_mode: CacheMode | str = ..., cache_ttl: int = ..., strict_api: bool = True, auto_split_codes: bool = False, consistency_mode: ConsistencyMode | str = ..., conflict_resolution: ConflictResolution | str = ..., output_order: OutputOrder | str = ..., allow_raw_override: bool = False, metadata_freshness_strict: bool = False, capture_full_response: bool = False, retry_max_attempts: int = 5, retry_transport_max_attempts: int | None = None, retry_base_delay: float = 0.5, retry_cap_delay: float = 8.0, retry_jitter_ratio: float = 1.0, retry_on_403: bool = False, retry_on_403_max_attempts: int = 2, http_client: httpx.AsyncClient | None = None, http2: bool = False, proxy: str | None = None, limits: httpx.Limits | None = None) -> None:
        """非同期クライアントを初期化する。"""
    async def aclose(self) -> None:
        """内部Clientをクローズする。"""
    async def __aenter__(self) -> AsyncBojClient:
        """非同期コンテキスト開始。"""
    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        """非同期コンテキスト終了。"""
