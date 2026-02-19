"""非JSONレスポンスのフォールバック動作テスト。"""

from __future__ import annotations

import httpx

from bojstat import BojClient, BojGatewayError


def test_html_400_is_mapped_to_gateway_error() -> None:
    """HTML 400 応答が JSONDecodeError で落ちないことを確認する。"""

    def handler(request: httpx.Request) -> httpx.Response:
        html = "<html><body><h1>Bad Request</h1></body></html>"
        return httpx.Response(
            status_code=400,
            content=html.encode("utf-8"),
            headers={"content-type": "text/html"},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://example.invalid/api/v1")

    with BojClient(
        http_client=http_client,
        base_url="https://example.invalid/api/v1",
        cache_mode="off",
        rate_limit_per_sec=1000.0,
    ) as client:
        try:
            client.metadata.get(db="INVALID")
            raised = False
        except BojGatewayError as exc:
            raised = True
            assert exc.status == 400
            assert exc.message_id == "UNPARSEABLE_RESPONSE"

    assert raised


def test_html_500_retries_and_then_succeeds() -> None:
    """HTML 500 応答が再試行され、次の200で成功することを確認する。"""

    state = {"calls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["calls"] += 1
        if state["calls"] == 1:
            html = "<html><body><h1>Internal Server Error</h1></body></html>"
            return httpx.Response(
                status_code=500,
                content=html.encode("utf-8"),
                headers={"content-type": "text/html"},
                request=request,
            )

        payload = {
            "STATUS": 200,
            "MESSAGEID": "M181000I",
            "MESSAGE": "ok",
            "DATE": "2025-12-02T13:13:14.587+09:00",
            "DB": "PR01",
            "RESULTSET": [],
        }
        return httpx.Response(status_code=200, json=payload, request=request)

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://example.invalid/api/v1")

    with BojClient(
        http_client=http_client,
        base_url="https://example.invalid/api/v1",
        cache_mode="off",
        rate_limit_per_sec=1000.0,
        retry_base_delay=0.0,
        retry_cap_delay=0.0,
    ) as client:
        frame = client.metadata.get(db="PR01")

    assert frame.meta.status == 200
    assert state["calls"] == 2
