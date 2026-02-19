from collections.abc import Mapping
from dataclasses import dataclass

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
    def __init__(self, rate_limit_per_sec: float) -> None: ...
    def acquire(self) -> float:
        """送信許可まで待機する。

        Returns:
            待機した秒数。
        """

class AsyncRateLimiter:
    """非同期用の最小間隔レート制御。"""
    def __init__(self, rate_limit_per_sec: float) -> None: ...
    async def acquire(self) -> float:
        """送信許可まで待機する。"""

def parse_retry_after(value: str | None) -> float | None:
    """Retry-Afterヘッダを秒へ変換する。"""
def should_retry_http_status(status_code: int, *, retry_on_403: bool, has_retry_after: bool) -> bool:
    """HTTPステータスから再試行可否を判定する。"""
def should_retry_transport_error(exc: Exception) -> bool:
    """通信例外の再試行可否を判定する。"""
def full_jitter_backoff(*, attempt: int, base: float, cap: float) -> float:
    """full jitter で待機秒を計算する。"""
def decide_wait_seconds(*, retry_after: float | None, local_wait: float, backoff: float) -> WaitDecision:
    """待機秒を統合決定する。"""
def build_request_headers(user_agent: str) -> Mapping[str, str]:
    """標準ヘッダを構築する。"""
