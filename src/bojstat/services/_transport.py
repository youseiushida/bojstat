"""サービス層向けトランスポート共通処理。"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping
from typing import Any

import httpx

from bojstat.config import RetryConfig
from bojstat.enums import Format, Lang
from bojstat.errors import (
    BojApiError,
    BojBadRequestError,
    BojGatewayError,
    BojServerError,
    BojTransportError,
    BojUnavailableError,
)
from bojstat.http import (
    AsyncRateLimiter,
    SyncRateLimiter,
    build_request_headers,
    decide_wait_seconds,
    full_jitter_backoff,
    parse_retry_after,
    should_retry_http_status,
    should_retry_transport_error,
)
from bojstat.parsers import parse_response
from bojstat.types import ParsedResponse


def _effective_transport_max_attempts(retry_config: RetryConfig) -> int:
    """通信例外時の最大試行回数を返す。"""

    configured = retry_config.transport_max_attempts
    if configured is None:
        return retry_config.max_attempts
    return max(1, configured)


def _compute_backoff_seconds(*, attempt: int, retry_config: RetryConfig) -> float:
    """再試行用バックオフ待機秒を計算する。"""

    jitter_ratio = max(0.0, retry_config.jitter_ratio)
    return full_jitter_backoff(
        attempt=attempt,
        base=retry_config.base_delay * jitter_ratio,
        cap=retry_config.cap_delay,
    )


def _parse_response_with_fallback(
    *,
    response: httpx.Response,
    requested_format: Format,
    lang: Lang,
) -> ParsedResponse:
    """レスポンスを解析し、失敗時はHTTPステータスでフォールバックする。

    Args:
        response: HTTPレスポンス。
        requested_format: 要求形式。
        lang: 要求言語。

    Returns:
        解析済みレスポンス。
    """

    try:
        return parse_response(
            response.content,
            requested_format=requested_format,
            lang=lang,
        )
    except Exception as exc:  # noqa: BLE001
        text = response.text
        status = int(response.status_code)
        return ParsedResponse(
            status=status,
            message_id="UNPARSEABLE_RESPONSE",
            message=(
                "APIレスポンスの本文を解析できませんでした。"
                f"fallback_status={status}, parser_error={type(exc).__name__}"
            ),
            date_raw=None,
            date_parsed=None,
            date_parse_warning=None,
            parameters={},
            next_position=None,
            rows=[],
            db=None,
            raw_response_excerpt=text[:2048],
            format=requested_format,
        )


def _make_api_error(
    parsed: ParsedResponse,
    *,
    request_url: str,
    capture_full_response: bool,
    raw_text: str,
) -> BojApiError:
    if parsed.message_id == "UNPARSEABLE_RESPONSE":
        klass = BojGatewayError
    elif parsed.status == 400:
        klass = BojBadRequestError
    elif parsed.status == 500:
        klass = BojServerError
    elif parsed.status == 503:
        klass = BojUnavailableError
    else:
        klass = BojApiError
    return klass(
        parsed.message,
        status=parsed.status,
        message_id=parsed.message_id,
        request_url=request_url,
        raw_response_excerpt=parsed.raw_response_excerpt,
        raw_response=raw_text if capture_full_response else None,
    )


def raise_for_api_error(
    parsed: ParsedResponse,
    *,
    request_url: str,
    capture_full_response: bool,
    raw_text: str,
) -> None:
    """エラーステータスのとき例外を送出する。"""

    if parsed.status == 200:
        return
    raise _make_api_error(
        parsed,
        request_url=request_url,
        capture_full_response=capture_full_response,
        raw_text=raw_text,
    )


def should_retry_response(
    *,
    parsed_status: int,
    http_status: int,
    headers: Mapping[str, str],
    retry_config: RetryConfig,
    attempt: int,
) -> bool:
    """レスポンスに対する再試行可否を判定する。"""

    if parsed_status in {500, 503}:
        return True

    retry_after = headers.get("Retry-After")
    has_retry_after = retry_after is not None
    if http_status == 403 and retry_config.retry_on_403 and has_retry_after:
        return attempt < retry_config.retry_on_403_max_attempts
    return should_retry_http_status(
        http_status,
        retry_on_403=retry_config.retry_on_403,
        has_retry_after=has_retry_after,
    )


def perform_sync_request(
    *,
    client: httpx.Client,
    endpoint: str,
    params: dict[str, Any],
    lang: Lang,
    format: Format,
    retry_config: RetryConfig,
    limiter: SyncRateLimiter,
    user_agent: str,
    capture_full_response: bool,
) -> tuple[ParsedResponse, str, str]:
    """同期GET要求を再試行つきで実行する。"""

    headers = dict(build_request_headers(user_agent))
    last_exception: Exception | None = None
    transport_max_attempts = _effective_transport_max_attempts(retry_config)
    total_attempts = max(retry_config.max_attempts, transport_max_attempts)
    for attempt in range(1, total_attempts + 1):
        limiter.acquire()
        try:
            response = client.get(endpoint, params=params, headers=headers)
        except Exception as exc:  # noqa: BLE001
            last_exception = exc
            if should_retry_transport_error(exc) and attempt < transport_max_attempts:
                backoff = _compute_backoff_seconds(
                    attempt=attempt,
                    retry_config=retry_config,
                )
                time.sleep(backoff)
                continue
            raise BojTransportError(str(exc)) from exc

        parsed = _parse_response_with_fallback(
            response=response,
            requested_format=format,
            lang=lang,
        )
        request_url = str(response.request.url)
        raw_text = response.text
        if should_retry_response(
            parsed_status=parsed.status,
            http_status=response.status_code,
            headers=response.headers,
            retry_config=retry_config,
            attempt=attempt,
        ) and attempt < retry_config.max_attempts:
            retry_after = parse_retry_after(response.headers.get("Retry-After"))
            backoff = _compute_backoff_seconds(
                attempt=attempt,
                retry_config=retry_config,
            )
            wait = decide_wait_seconds(retry_after=retry_after, local_wait=0.0, backoff=backoff)
            time.sleep(wait.seconds)
            continue

        if parsed.status != 200:
            raise _make_api_error(
                parsed,
                request_url=request_url,
                capture_full_response=capture_full_response,
                raw_text=raw_text,
            )
        return parsed, request_url, raw_text

    if last_exception is not None:
        raise BojTransportError(str(last_exception)) from last_exception
    raise BojTransportError("要求の実行に失敗しました。")


async def perform_async_request(
    *,
    client: httpx.AsyncClient,
    endpoint: str,
    params: dict[str, Any],
    lang: Lang,
    format: Format,
    retry_config: RetryConfig,
    limiter: AsyncRateLimiter,
    user_agent: str,
    capture_full_response: bool,
) -> tuple[ParsedResponse, str, str]:
    """非同期GET要求を再試行つきで実行する。"""

    headers = dict(build_request_headers(user_agent))
    last_exception: Exception | None = None
    transport_max_attempts = _effective_transport_max_attempts(retry_config)
    total_attempts = max(retry_config.max_attempts, transport_max_attempts)
    for attempt in range(1, total_attempts + 1):
        await limiter.acquire()
        try:
            response = await client.get(endpoint, params=params, headers=headers)
        except Exception as exc:  # noqa: BLE001
            last_exception = exc
            if should_retry_transport_error(exc) and attempt < transport_max_attempts:
                backoff = _compute_backoff_seconds(
                    attempt=attempt,
                    retry_config=retry_config,
                )
                await asyncio.sleep(backoff)
                continue
            raise BojTransportError(str(exc)) from exc

        parsed = _parse_response_with_fallback(
            response=response,
            requested_format=format,
            lang=lang,
        )
        request_url = str(response.request.url)
        raw_text = response.text
        if should_retry_response(
            parsed_status=parsed.status,
            http_status=response.status_code,
            headers=response.headers,
            retry_config=retry_config,
            attempt=attempt,
        ) and attempt < retry_config.max_attempts:
            retry_after = parse_retry_after(response.headers.get("Retry-After"))
            backoff = _compute_backoff_seconds(
                attempt=attempt,
                retry_config=retry_config,
            )
            wait = decide_wait_seconds(retry_after=retry_after, local_wait=0.0, backoff=backoff)
            await asyncio.sleep(wait.seconds)
            continue

        if parsed.status != 200:
            raise _make_api_error(
                parsed,
                request_url=request_url,
                capture_full_response=capture_full_response,
                raw_text=raw_text,
            )
        return parsed, request_url, raw_text

    if last_exception is not None:
        raise BojTransportError(str(last_exception)) from last_exception
    raise BojTransportError("要求の実行に失敗しました。")
