"""resume_token のテスト。"""

from __future__ import annotations

import json

import httpx
import pytest

from bojstat import BojClient
from bojstat.config import NORMALIZER_VERSION, PARSER_VERSION, SCHEMA_VERSION
from bojstat.errors import BojResumeTokenMismatchError
from bojstat.resume import create_resume_token


def test_resume_token_mismatch_detected_before_request() -> None:
    called = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        called["n"] += 1
        payload = {
            "STATUS": 200,
            "MESSAGEID": "M181000I",
            "MESSAGE": "ok",
            "DATE": "2025-12-02T13:13:14.587+09:00",
            "PARAMETER": {},
            "NEXTPOSITION": None,
            "RESULTSET": [],
        }
        return httpx.Response(
            status_code=200,
            content=json.dumps(payload).encode("utf-8"),
            request=request,
        )

    token = create_resume_token(
        api="code",
        api_origin="https://example.invalid/api/v1",
        request_fingerprint="dummy",
        chunk_index=0,
        next_position=2,
        lang="JP",
        format="JSON",
        parser_version=PARSER_VERSION,
        normalizer_version=NORMALIZER_VERSION,
        schema_version=SCHEMA_VERSION,
        code_order_map={"AAA": 0},
    )

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://example.invalid/api/v1")

    with BojClient(
        http_client=http_client,
        base_url="https://example.invalid/api/v1",
        cache_mode="off",
        rate_limit_per_sec=1000.0,
    ) as client:
        with pytest.raises(BojResumeTokenMismatchError):
            client.data.get_by_code(db="CO", code=["AAA"], resume_token=token)

    assert called["n"] == 0
