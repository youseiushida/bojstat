"""パーサのテスト。"""

from __future__ import annotations

import json

from bojstat.enums import Format, Lang
from bojstat.parsers import parse_response
from bojstat.parsers.csv_parser import parse_csv_response
from bojstat.parsers.json_parser import parse_json_response


def test_parse_json_nested_values() -> None:
    payload = {
        "STATUS": 200,
        "MESSAGEID": "M181000I",
        "MESSAGE": "ok",
        "DATE": "2025-12-02T13:13:14.587+09:00",
        "PARAMETER": {"DB": "CO"},
        "NEXTPOSITION": None,
        "RESULTSET": [
            {
                "SERIES CODE": "AAA",
                "VALUES": {
                    "SURVEY DATES": ["202401", "202402"],
                    "VALUES": ["1.0", None],
                },
            }
        ],
    }
    parsed = parse_json_response(json.dumps(payload, ensure_ascii=False))
    assert parsed.status == 200
    assert parsed.message_id == "M181000I"
    assert len(parsed.rows) == 1


def test_parse_csv_blank_next_position() -> None:
    csv_text = "\n".join(
        [
            "STATUS,200",
            "MESSAGEID,M181000I",
            "MESSAGE,ok",
            "DATE,2025-12-02T13:13:14.587+09:00",
            "PARAMETER,DB,CO",
            "NEXTPOSITION,",
            "SERIES_CODE,NAME_OF_TIME_SERIES_J,SURVEY_DATES,VALUES",
            "AAA,系列,202401,1.0",
        ]
    )
    parsed = parse_csv_response(csv_text)
    assert parsed.next_position is None
    assert parsed.rows[0]["SERIES_CODE"] == "AAA"


def test_parse_response_prefers_json_error_even_if_csv_requested() -> None:
    payload = {
        "STATUS": 400,
        "MESSAGEID": "M181005E",
        "MESSAGE": "DB名が正しくありません。",
        "DATE": "2025-12-02T14:00:36.836+09:00",
    }
    parsed = parse_response(
        json.dumps(payload).encode("utf-8"),
        requested_format=Format.CSV,
        lang=Lang.JP,
    )
    assert parsed.format == Format.JSON
    assert parsed.status == 400
