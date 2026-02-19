"""公開クライアント実装。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from bojstat.cache import FileCache
from bojstat.config import CacheConfig, ClientConfig, RetryConfig
from bojstat.enums import CacheMode, ConflictResolution, ConsistencyMode, Format, Lang, OutputOrder
from bojstat.errors_catalog import ErrorClassifier
from bojstat.http import AsyncRateLimiter, SyncRateLimiter
from bojstat.services.data import AsyncDataService, DataService
from bojstat.services.metadata import AsyncMetadataService, MetadataService
from bojstat.validation import normalize_format, normalize_lang, validate_strict_auto_split


class BojClient:
    """日本銀行APIの同期クライアント。"""

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        base_url: str = "https://www.stat-search.boj.or.jp/api/v1",
        lang: Lang | str = Lang.JP,
        format: Format | str = Format.JSON,
        user_agent: str = "bojstat/0.1.0",
        rate_limit_per_sec: float = 1.0,
        cache_dir: str | Path | None = None,
        cache_mode: CacheMode | str = CacheMode.IF_STALE,
        cache_ttl: int = 24 * 60 * 60,
        strict_api: bool = True,
        auto_split_codes: bool = False,
        consistency_mode: ConsistencyMode | str = ConsistencyMode.STRICT,
        conflict_resolution: ConflictResolution | str = ConflictResolution.LATEST_LAST_UPDATE,
        output_order: OutputOrder | str = OutputOrder.CANONICAL,
        allow_raw_override: bool = False,
        metadata_freshness_strict: bool = False,
        capture_full_response: bool = False,
        retry_max_attempts: int = 5,
        retry_transport_max_attempts: int | None = None,
        retry_base_delay: float = 0.5,
        retry_cap_delay: float = 8.0,
        retry_jitter_ratio: float = 1.0,
        retry_on_403: bool = False,
        retry_on_403_max_attempts: int = 2,
        http_client: httpx.Client | None = None,
        http2: bool = False,
        proxy: str | None = None,
        limits: httpx.Limits | None = None,
    ) -> None:
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

        validate_strict_auto_split(strict_api=strict_api, auto_split_codes=auto_split_codes)
        if retry_max_attempts < 1:
            raise ValueError("retry_max_attempts は1以上を指定してください。")
        if retry_transport_max_attempts is not None and retry_transport_max_attempts < 1:
            raise ValueError("retry_transport_max_attempts は1以上を指定してください。")
        if retry_jitter_ratio <= 0:
            raise ValueError("retry_jitter_ratio は0より大きい値を指定してください。")

        lang_norm = normalize_lang(lang)
        format_norm = normalize_format(format)
        cache_mode_norm = cache_mode if isinstance(cache_mode, CacheMode) else CacheMode(cache_mode)
        consistency_norm = (
            consistency_mode
            if isinstance(consistency_mode, ConsistencyMode)
            else ConsistencyMode(consistency_mode)
        )
        conflict_norm = (
            conflict_resolution
            if isinstance(conflict_resolution, ConflictResolution)
            else ConflictResolution(conflict_resolution)
        )
        output_order_norm = (
            output_order if isinstance(output_order, OutputOrder) else OutputOrder(output_order)
        )

        self._owns_client = http_client is None
        if http_client is None:
            client_kwargs: dict[str, Any] = {
                "base_url": base_url,
                "timeout": timeout,
                "http2": http2,
            }
            if proxy is not None:
                client_kwargs["proxy"] = proxy
            if limits is not None:
                client_kwargs["limits"] = limits
            self._http_client = httpx.Client(
                **client_kwargs,
            )
        else:
            self._http_client = http_client

        cache_conf = CacheConfig(
            mode=cache_mode_norm,
            dir=Path(cache_dir) if cache_dir is not None else None,
            ttl_seconds=cache_ttl,
        )
        self._config = ClientConfig(
            base_url=base_url,
            timeout=timeout,
            lang=lang_norm,
            format=format_norm,
            user_agent=user_agent,
            rate_limit_per_sec=rate_limit_per_sec,
            strict_api=strict_api,
            auto_split_codes=auto_split_codes,
            consistency_mode=consistency_norm,
            conflict_resolution=conflict_norm,
            output_order=output_order_norm,
            allow_raw_override=allow_raw_override,
            metadata_freshness_strict=metadata_freshness_strict,
            capture_full_response=capture_full_response,
            cache=cache_conf,
        )
        self._retry = RetryConfig(
            max_attempts=retry_max_attempts,
            transport_max_attempts=retry_transport_max_attempts,
            base_delay=retry_base_delay,
            cap_delay=retry_cap_delay,
            jitter_ratio=retry_jitter_ratio,
            retry_on_403=retry_on_403,
            retry_on_403_max_attempts=retry_on_403_max_attempts,
        )
        self._cache = FileCache(cache_dir=cache_conf.dir, ttl_seconds=cache_conf.ttl_seconds)
        self._limiter = SyncRateLimiter(rate_limit_per_sec=rate_limit_per_sec)

        self.data = DataService(
            client=self._http_client,
            config=self._config,
            retry_config=self._retry,
            cache=self._cache,
            limiter=self._limiter,
        )
        self.metadata = MetadataService(
            client=self._http_client,
            config=self._config,
            retry_config=self._retry,
            cache=self._cache,
            limiter=self._limiter,
        )
        self.errors = ErrorClassifier()

    def close(self) -> None:
        """内部Clientをクローズする。"""

        if self._owns_client:
            self._http_client.close()

    def __enter__(self) -> "BojClient":
        """コンテキスト開始。"""

        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        """コンテキスト終了。"""

        self.close()


class AsyncBojClient:
    """日本銀行APIの非同期クライアント。"""

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        base_url: str = "https://www.stat-search.boj.or.jp/api/v1",
        lang: Lang | str = Lang.JP,
        format: Format | str = Format.JSON,
        user_agent: str = "bojstat/0.1.0",
        rate_limit_per_sec: float = 1.0,
        cache_dir: str | Path | None = None,
        cache_mode: CacheMode | str = CacheMode.IF_STALE,
        cache_ttl: int = 24 * 60 * 60,
        strict_api: bool = True,
        auto_split_codes: bool = False,
        consistency_mode: ConsistencyMode | str = ConsistencyMode.STRICT,
        conflict_resolution: ConflictResolution | str = ConflictResolution.LATEST_LAST_UPDATE,
        output_order: OutputOrder | str = OutputOrder.CANONICAL,
        allow_raw_override: bool = False,
        metadata_freshness_strict: bool = False,
        capture_full_response: bool = False,
        retry_max_attempts: int = 5,
        retry_transport_max_attempts: int | None = None,
        retry_base_delay: float = 0.5,
        retry_cap_delay: float = 8.0,
        retry_jitter_ratio: float = 1.0,
        retry_on_403: bool = False,
        retry_on_403_max_attempts: int = 2,
        http_client: httpx.AsyncClient | None = None,
        http2: bool = False,
        proxy: str | None = None,
        limits: httpx.Limits | None = None,
    ) -> None:
        """非同期クライアントを初期化する。"""

        validate_strict_auto_split(strict_api=strict_api, auto_split_codes=auto_split_codes)
        if retry_max_attempts < 1:
            raise ValueError("retry_max_attempts は1以上を指定してください。")
        if retry_transport_max_attempts is not None and retry_transport_max_attempts < 1:
            raise ValueError("retry_transport_max_attempts は1以上を指定してください。")
        if retry_jitter_ratio <= 0:
            raise ValueError("retry_jitter_ratio は0より大きい値を指定してください。")

        lang_norm = normalize_lang(lang)
        format_norm = normalize_format(format)
        cache_mode_norm = cache_mode if isinstance(cache_mode, CacheMode) else CacheMode(cache_mode)
        consistency_norm = (
            consistency_mode
            if isinstance(consistency_mode, ConsistencyMode)
            else ConsistencyMode(consistency_mode)
        )
        conflict_norm = (
            conflict_resolution
            if isinstance(conflict_resolution, ConflictResolution)
            else ConflictResolution(conflict_resolution)
        )
        output_order_norm = (
            output_order if isinstance(output_order, OutputOrder) else OutputOrder(output_order)
        )

        self._owns_client = http_client is None
        if http_client is None:
            client_kwargs: dict[str, Any] = {
                "base_url": base_url,
                "timeout": timeout,
                "http2": http2,
            }
            if proxy is not None:
                client_kwargs["proxy"] = proxy
            if limits is not None:
                client_kwargs["limits"] = limits
            self._http_client = httpx.AsyncClient(
                **client_kwargs,
            )
        else:
            self._http_client = http_client

        cache_conf = CacheConfig(
            mode=cache_mode_norm,
            dir=Path(cache_dir) if cache_dir is not None else None,
            ttl_seconds=cache_ttl,
        )
        self._config = ClientConfig(
            base_url=base_url,
            timeout=timeout,
            lang=lang_norm,
            format=format_norm,
            user_agent=user_agent,
            rate_limit_per_sec=rate_limit_per_sec,
            strict_api=strict_api,
            auto_split_codes=auto_split_codes,
            consistency_mode=consistency_norm,
            conflict_resolution=conflict_norm,
            output_order=output_order_norm,
            allow_raw_override=allow_raw_override,
            metadata_freshness_strict=metadata_freshness_strict,
            capture_full_response=capture_full_response,
            cache=cache_conf,
        )
        self._retry = RetryConfig(
            max_attempts=retry_max_attempts,
            transport_max_attempts=retry_transport_max_attempts,
            base_delay=retry_base_delay,
            cap_delay=retry_cap_delay,
            jitter_ratio=retry_jitter_ratio,
            retry_on_403=retry_on_403,
            retry_on_403_max_attempts=retry_on_403_max_attempts,
        )
        self._cache = FileCache(cache_dir=cache_conf.dir, ttl_seconds=cache_conf.ttl_seconds)
        self._limiter = AsyncRateLimiter(rate_limit_per_sec=rate_limit_per_sec)

        self.data = AsyncDataService(
            client=self._http_client,
            config=self._config,
            retry_config=self._retry,
            cache=self._cache,
            limiter=self._limiter,
        )
        self.metadata = AsyncMetadataService(
            client=self._http_client,
            config=self._config,
            retry_config=self._retry,
            cache=self._cache,
            limiter=self._limiter,
        )
        self.errors = ErrorClassifier()

    async def aclose(self) -> None:
        """内部Clientをクローズする。"""

        if self._owns_client:
            await self._http_client.aclose()

    async def __aenter__(self) -> "AsyncBojClient":
        """非同期コンテキスト開始。"""

        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        """非同期コンテキスト終了。"""

        await self.aclose()
