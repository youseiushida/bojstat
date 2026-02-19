"""strict/auto_split 契約と再試行のテスト。"""

from __future__ import annotations

import json

import httpx
import pytest

from bojstat import BojClient
from bojstat.errors import BojTransportError


def _json_response(
    request: httpx.Request,
    payload: dict[str, object],
    *,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        content=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        request=request,
    )


def test_client_rejects_strict_and_auto_split_true() -> None:
    with pytest.raises(ValueError):
        BojClient(strict_api=True, auto_split_codes=True)


def test_auto_split_codes_chunks_by_250() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        code_param = request.url.params.get("CODE", "")
        calls.append(len([x for x in code_param.split(",") if x]))
        payload = {
            "STATUS": 200,
            "MESSAGEID": "M181030I",
            "MESSAGE": "no data",
            "DATE": "2025-12-02T13:13:14.587+09:00",
            "PARAMETER": {},
            "NEXTPOSITION": None,
            "RESULTSET": [],
        }
        return _json_response(request, payload)

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://example.invalid/api/v1")

    codes = [f"C{i}@D" for i in range(300)]
    with BojClient(
        http_client=http_client,
        base_url="https://example.invalid/api/v1",
        strict_api=False,
        auto_split_codes=True,
        cache_mode="off",
        rate_limit_per_sec=1000.0,
    ) as client:
        frame = client.data.get_by_code(db="CO", code=codes)

    assert calls == [250, 50]
    assert frame.records == []


def test_retries_on_body_status_500_then_succeeds() -> None:
    counter = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        counter["n"] += 1
        if counter["n"] == 1:
            payload = {
                "STATUS": 500,
                "MESSAGEID": "M181090S",
                "MESSAGE": "temporary",
                "DATE": "2025-12-02T13:13:14.587+09:00",
            }
            return _json_response(request, payload)

        payload = {
            "STATUS": 200,
            "MESSAGEID": "M181000I",
            "MESSAGE": "ok",
            "DATE": "2025-12-02T13:13:15.000+09:00",
            "PARAMETER": {},
            "NEXTPOSITION": None,
            "RESULTSET": [
                {
                    "SERIES CODE": "AAA",
                    "FREQUENCY": "MONTHLY",
                    "LAST UPDATE": "20251001",
                    "VALUES": {
                        "SURVEY DATES": ["202501"],
                        "VALUES": ["1.0"],
                    },
                }
            ],
        }
        return _json_response(request, payload)

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://example.invalid/api/v1")

    with BojClient(
        http_client=http_client,
        base_url="https://example.invalid/api/v1",
        cache_mode="off",
        retry_base_delay=0.0,
        retry_cap_delay=0.0,
        rate_limit_per_sec=1000.0,
    ) as client:
        frame = client.data.get_by_code(db="CO", code=["AAA"])

    assert counter["n"] == 2
    assert len(frame.records) == 1


def test_retry_transport_max_attempts_can_exceed_retry_max_attempts() -> None:
    state = {"calls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["calls"] += 1
        if state["calls"] < 3:
            raise httpx.ConnectError("temporary", request=request)
        payload = {
            "STATUS": 200,
            "MESSAGEID": "M181030I",
            "MESSAGE": "no data",
            "DATE": "2025-12-02T13:13:14.587+09:00",
            "PARAMETER": {},
            "NEXTPOSITION": None,
            "RESULTSET": [],
        }
        return _json_response(request, payload)

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://example.invalid/api/v1")

    with BojClient(
        http_client=http_client,
        base_url="https://example.invalid/api/v1",
        cache_mode="off",
        retry_max_attempts=2,
        retry_transport_max_attempts=3,
        retry_base_delay=0.0,
        retry_cap_delay=0.0,
        rate_limit_per_sec=1000.0,
    ) as client:
        frame = client.data.get_by_code(db="CO", code=["AAA"])

    assert frame.meta.status == 200
    assert state["calls"] == 3


def test_retry_transport_max_attempts_limits_transport_retries() -> None:
    state = {"calls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["calls"] += 1
        raise httpx.ConnectError("temporary", request=request)

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://example.invalid/api/v1")

    with BojClient(
        http_client=http_client,
        base_url="https://example.invalid/api/v1",
        cache_mode="off",
        retry_max_attempts=5,
        retry_transport_max_attempts=2,
        retry_base_delay=0.0,
        retry_cap_delay=0.0,
        rate_limit_per_sec=1000.0,
    ) as client:
        with pytest.raises(BojTransportError):
            client.data.get_by_code(db="CO", code=["AAA"])

    assert state["calls"] == 2


def test_client_rejects_invalid_retry_parameters() -> None:
    with pytest.raises(ValueError):
        BojClient(retry_transport_max_attempts=0)
    with pytest.raises(ValueError):
        BojClient(retry_jitter_ratio=0.0)
