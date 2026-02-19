"""DataService(get_by_code) のテスト。"""

from __future__ import annotations

import json

import httpx
import pytest

from bojstat import BojClient
from bojstat.errors import BojPaginationStalledError


def _json_response(payload: dict[str, object], request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        status_code=200,
        content=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        request=request,
    )


def test_get_by_code_auto_paginates_and_sorts() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        start_pos = int(request.url.params.get("STARTPOSITION", "1"))
        calls.append(start_pos)
        if start_pos == 1:
            payload = {
                "STATUS": 200,
                "MESSAGEID": "M181000I",
                "MESSAGE": "ok",
                "DATE": "2025-12-02T13:13:14.587+09:00",
                "PARAMETER": {"DB": "CO", "STARTPOSITION": "1"},
                "NEXTPOSITION": 2,
                "RESULTSET": [
                    {
                        "SERIES CODE": "CODE_A",
                        "NAME OF TIME SERIES": "A",
                        "FREQUENCY": "MONTHLY",
                        "LAST UPDATE": "20251001",
                        "VALUES": {
                            "SURVEY DATES": ["202501", "202502"],
                            "VALUES": ["1.0", "2.0"],
                        },
                    }
                ],
            }
            return _json_response(payload, request)

        payload = {
            "STATUS": 200,
            "MESSAGEID": "M181000I",
            "MESSAGE": "ok",
            "DATE": "2025-12-02T13:13:15.000+09:00",
            "PARAMETER": {"DB": "CO", "STARTPOSITION": "2"},
            "NEXTPOSITION": None,
            "RESULTSET": [
                {
                    "SERIES CODE": "CODE_B",
                    "NAME OF TIME SERIES": "B",
                    "FREQUENCY": "MONTHLY",
                    "LAST UPDATE": "20251001",
                    "VALUES": {
                        "SURVEY DATES": ["202501"],
                        "VALUES": ["3.0"],
                    },
                }
            ],
        }
        return _json_response(payload, request)

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://example.invalid/api/v1")

    with BojClient(
        http_client=http_client,
        base_url="https://example.invalid/api/v1",
        cache_mode="off",
        rate_limit_per_sec=1000.0,
    ) as client:
        frame = client.data.get_by_code(
            db="co",
            code=["CODE_A", "CODE_B"],
            start="202501",
            end="202512",
        )

    assert calls == [1, 2]
    assert [r.series_code for r in frame.records] == ["CODE_A", "CODE_A", "CODE_B"]
    assert frame.meta.next_position is None
    assert frame.meta.resume_token is None


def test_get_by_code_detects_stalled_next_position() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = {
            "STATUS": 200,
            "MESSAGEID": "M181000I",
            "MESSAGE": "ok",
            "DATE": "2025-12-02T13:13:14.587+09:00",
            "PARAMETER": {"DB": "CO", "STARTPOSITION": "1"},
            "NEXTPOSITION": 1,
            "RESULTSET": [],
        }
        return _json_response(payload, request)

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://example.invalid/api/v1")

    with BojClient(
        http_client=http_client,
        base_url="https://example.invalid/api/v1",
        cache_mode="off",
        rate_limit_per_sec=1000.0,
    ) as client:
        with pytest.raises(BojPaginationStalledError):
            client.data.get_by_code(db="co", code=["CODE_A"])


def test_get_by_code_accepts_year_periods() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["start"] = str(request.url.params.get("STARTDATE", ""))
        captured["end"] = str(request.url.params.get("ENDDATE", ""))
        payload = {
            "STATUS": 200,
            "MESSAGEID": "M181030I",
            "MESSAGE": "no data",
            "DATE": "2025-12-02T13:13:14.587+09:00",
            "PARAMETER": {},
            "NEXTPOSITION": None,
            "RESULTSET": [],
        }
        return _json_response(payload, request)

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://example.invalid/api/v1")

    with BojClient(
        http_client=http_client,
        base_url="https://example.invalid/api/v1",
        cache_mode="off",
        rate_limit_per_sec=1000.0,
    ) as client:
        frame = client.data.get_by_code(
            db="co",
            code=["CODE_A"],
            start="2024",
            end="2025",
        )

    assert frame.meta.status == 200
    assert captured == {"start": "2024", "end": "2025"}
