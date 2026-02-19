"""AsyncBojClient のテスト。"""

from __future__ import annotations

import asyncio
import json

import httpx

from bojstat import AsyncBojClient


def test_async_get_by_layer_basic() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = {
            "STATUS": 200,
            "MESSAGEID": "M181000I",
            "MESSAGE": "ok",
            "DATE": "2025-12-02T13:13:14.587+09:00",
            "PARAMETER": {},
            "NEXTPOSITION": None,
            "RESULTSET": [
                {
                    "SERIES CODE": "AAA",
                    "FREQUENCY": "QUARTERLY",
                    "LAST UPDATE": "20251001",
                    "VALUES": {
                        "SURVEY DATES": ["202501"],
                        "VALUES": ["1.0"],
                    },
                }
            ],
        }
        return httpx.Response(
            status_code=200,
            content=json.dumps(payload).encode("utf-8"),
            request=request,
        )

    async def run() -> None:
        transport = httpx.MockTransport(handler)
        http_client = httpx.AsyncClient(
            transport=transport,
            base_url="https://example.invalid/api/v1",
        )
        async with AsyncBojClient(
            http_client=http_client,
            base_url="https://example.invalid/api/v1",
            cache_mode="off",
            rate_limit_per_sec=1000.0,
        ) as client:
            frame = await client.data.get_by_layer(
                db="MD10",
                frequency="Q",
                layer="1,*",
            )
            assert len(frame.records) == 1

    asyncio.run(run())
