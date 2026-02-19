"""メタデータ取得とエラー分類のテスト。"""

from __future__ import annotations

import json

import httpx

from bojstat import BojClient


def test_metadata_get_and_find() -> None:
    csv_text = "\n".join(
        [
            "STATUS,200",
            "MESSAGEID,M181000I",
            "MESSAGE,ok",
            "DATE,2025-12-02T13:13:14.587+09:00",
            "DB,FM08",
            "SERIES_CODE,NAME_OF_TIME_SERIES_J,UNIT_J,FREQUENCY,CATEGORY_J,LAYER1,LAYER2,LAYER3,LAYER4,LAYER5,START_OF_THE_TIME_SERIES,END_OF_THE_TIME_SERIES,LAST_UPDATE,NOTES_J",
            "FXERD01,ドル・円,円,DAILY,外国為替,1,1,0,0,0,19990101,20251231,20251001,備考",
            ",見出し,,,,1,0,0,0,0,,,,",
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            content=csv_text.encode("shift_jis", errors="replace"),
            request=request,
        )

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://example.invalid/api/v1")

    with BojClient(
        http_client=http_client,
        base_url="https://example.invalid/api/v1",
        format="csv",
        cache_mode="off",
        rate_limit_per_sec=1000.0,
    ) as client:
        frame = client.metadata.get(db="fm08")
        filtered = frame.find(name_contains="ドル・円")

    assert len(frame.records) == 2
    assert filtered.series_codes == ["FXERD01"]


def test_error_classifier_known_and_unknown() -> None:
    with BojClient(cache_mode="off") as client:
        known = client.errors.classify(status=400, message_id="M181014E")
        unknown = client.errors.classify(message_id="M181999E")

    assert known.category == "frequency_mismatch"
    assert known.observation_key == "400:M181014E"
    assert unknown.category == "unknown"
    assert unknown.confidence == 0.0


def test_json_error_raised_on_bad_request() -> None:
    payload = {
        "STATUS": 400,
        "MESSAGEID": "M181005E",
        "MESSAGE": "DB名が正しくありません。",
        "DATE": "2025-12-02T14:00:36.836+09:00",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            content=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
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
        except Exception as exc:  # noqa: BLE001
            raised = True
            assert "DB名" in str(exc)

    assert raised
