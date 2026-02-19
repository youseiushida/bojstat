"""HTTP実行補助。"""

from __future__ import annotations

import asyncio
import random
import threading
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(slots=True)
class WaitDecision:
    """待機時間決定結果。

    Attributes:
        seconds: 待機秒。
        source: 待機根拠。
    """

    seconds: float
    source: str


class SyncRateLimiter:
    """同期用の最小間隔レート制御。"""

    def __init__(self, rate_limit_per_sec: float) -> None:
        self._min_interval = 1.0 / rate_limit_per_sec if rate_limit_per_sec > 0 else 0.0
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def acquire(self) -> float:
        """送信許可まで待機する。

        Returns:
            待機した秒数。
        """

        if self._min_interval <= 0:
            return 0.0
        with self._lock:
            now = time.monotonic()
            wait = max(0.0, self._next_allowed - now)
            if wait > 0:
                time.sleep(wait)
                now = time.monotonic()
            self._next_allowed = now + self._min_interval
            return wait


class AsyncRateLimiter:
    """非同期用の最小間隔レート制御。"""

    def __init__(self, rate_limit_per_sec: float) -> None:
        self._min_interval = 1.0 / rate_limit_per_sec if rate_limit_per_sec > 0 else 0.0
        self._lock = asyncio.Lock()
        self._next_allowed = 0.0

    async def acquire(self) -> float:
        """送信許可まで待機する。"""

        if self._min_interval <= 0:
            return 0.0
        async with self._lock:
            now = time.monotonic()
            wait = max(0.0, self._next_allowed - now)
            if wait > 0:
                await asyncio.sleep(wait)
                now = time.monotonic()
            self._next_allowed = now + self._min_interval
            return wait


def parse_retry_after(value: str | None) -> float | None:
    """Retry-Afterヘッダを秒へ変換する。"""

    if not value:
        return None
    text = value.strip()
    if text.isdigit():
        return float(text)
    try:
        dt = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None
    return max(0.0, dt.timestamp() - time.time())


def should_retry_http_status(
    status_code: int,
    *,
    retry_on_403: bool,
    has_retry_after: bool,
) -> bool:
    """HTTPステータスから再試行可否を判定する。"""

    if status_code in {429, 500, 503}:
        return True
    if status_code == 403 and retry_on_403 and has_retry_after:
        return True
    return False


def should_retry_transport_error(exc: Exception) -> bool:
    """通信例外の再試行可否を判定する。"""

    retryable = (
        httpx.TimeoutException,
        httpx.ConnectError,
        httpx.ReadError,
        httpx.RemoteProtocolError,
    )
    return isinstance(exc, retryable)


def full_jitter_backoff(*, attempt: int, base: float, cap: float) -> float:
    """full jitter で待機秒を計算する。"""

    upper = min(cap, base * (2 ** attempt))
    return random.uniform(0.0, upper)


def decide_wait_seconds(
    *,
    retry_after: float | None,
    local_wait: float,
    backoff: float,
) -> WaitDecision:
    """待機秒を統合決定する。"""

    if retry_after is None:
        selected = max(local_wait, backoff)
        source = "local_or_backoff"
    else:
        selected = max(retry_after, local_wait, backoff)
        source = "retry_after"
    return WaitDecision(seconds=selected, source=source)


def build_request_headers(user_agent: str) -> Mapping[str, str]:
    """標準ヘッダを構築する。"""

    return {
        "Accept-Encoding": "gzip",
        "User-Agent": user_agent,
    }
