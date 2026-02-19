import httpx
from bojstat.config import RetryConfig as RetryConfig
from bojstat.enums import Format as Format, Lang as Lang
from bojstat.errors import BojApiError as BojApiError, BojBadRequestError as BojBadRequestError, BojGatewayError as BojGatewayError, BojServerError as BojServerError, BojTransportError as BojTransportError, BojUnavailableError as BojUnavailableError
from bojstat.http import AsyncRateLimiter as AsyncRateLimiter, SyncRateLimiter as SyncRateLimiter, build_request_headers as build_request_headers, decide_wait_seconds as decide_wait_seconds, full_jitter_backoff as full_jitter_backoff, parse_retry_after as parse_retry_after, should_retry_http_status as should_retry_http_status, should_retry_transport_error as should_retry_transport_error
from bojstat.parsers import parse_response as parse_response
from bojstat.types import ParsedResponse as ParsedResponse
from collections.abc import Mapping
from typing import Any

def raise_for_api_error(parsed: ParsedResponse, *, request_url: str, capture_full_response: bool, raw_text: str) -> None:
    """エラーステータスのとき例外を送出する。"""
def should_retry_response(*, parsed_status: int, http_status: int, headers: Mapping[str, str], retry_config: RetryConfig, attempt: int) -> bool:
    """レスポンスに対する再試行可否を判定する。"""
def perform_sync_request(*, client: httpx.Client, endpoint: str, params: dict[str, Any], lang: Lang, format: Format, retry_config: RetryConfig, limiter: SyncRateLimiter, user_agent: str, capture_full_response: bool) -> tuple[ParsedResponse, str, str]:
    """同期GET要求を再試行つきで実行する。"""
async def perform_async_request(*, client: httpx.AsyncClient, endpoint: str, params: dict[str, Any], lang: Lang, format: Format, retry_config: RetryConfig, limiter: AsyncRateLimiter, user_agent: str, capture_full_response: bool) -> tuple[ParsedResponse, str, str]:
    """非同期GET要求を再試行つきで実行する。"""
