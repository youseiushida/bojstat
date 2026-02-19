"""CSVレスポンスパーサ。"""

from __future__ import annotations

import csv
from io import StringIO
from typing import Any

from bojstat.enums import Format
from bojstat.normalize import normalize_key, parse_date_tolerant
from bojstat.types import ParsedResponse


def _trim_row(row: list[str]) -> list[str]:
    return [cell.strip() for cell in row]


def parse_csv_response(text: str) -> ParsedResponse:
    """CSV本文を解析して共通形式へ変換する。

    Args:
        text: デコード済みCSV文字列。

    Returns:
        解析結果。
    """

    reader = csv.reader(StringIO(text))
    rows = [_trim_row(row) for row in reader if any(cell.strip() for cell in row)]

    status = 0
    message_id = ""
    message = ""
    date_raw: str | None = None
    date_parsed = None
    date_parse_warning: str | None = None
    parameters: dict[str, str | None] = {}
    next_position: int | None = None
    db: str | None = None

    data_header: list[str] | None = None
    data_rows: list[dict[str, Any]] = []

    for row in rows:
        key = normalize_key(row[0])
        if key == "STATUS":
            status = int(row[1]) if len(row) > 1 and row[1] else 0
            continue
        if key == "MESSAGEID":
            message_id = row[1] if len(row) > 1 else ""
            continue
        if key == "MESSAGE":
            message = row[1] if len(row) > 1 else ""
            continue
        if key == "DATE":
            date_raw = row[1] if len(row) > 1 and row[1] else None
            date_parsed, date_parse_warning = parse_date_tolerant(date_raw)
            continue
        if key == "PARAMETER":
            if len(row) > 1:
                value = row[2] if len(row) > 2 and row[2] else None
                parameters[normalize_key(row[1])] = value
            continue
        if key == "NEXTPOSITION":
            if len(row) > 1 and row[1]:
                next_position = int(row[1])
            continue
        if key == "DB":
            db = row[1] if len(row) > 1 and row[1] else None
            continue

        looks_like_header = {
            "SERIES_CODE",
            "NAME_OF_TIME_SERIES_J",
            "NAME_OF_TIME_SERIES",
        }
        normalized_row = [normalize_key(cell) for cell in row]
        if data_header is None and any(cell in looks_like_header for cell in normalized_row):
            data_header = [normalize_key(cell) for cell in row]
            continue

        if data_header is not None:
            mapped: dict[str, Any] = {}
            for idx, header in enumerate(data_header):
                if not header:
                    continue
                mapped[header] = row[idx] if idx < len(row) else ""
            data_rows.append(mapped)

    return ParsedResponse(
        status=status,
        message_id=message_id,
        message=message,
        date_raw=date_raw,
        date_parsed=date_parsed,
        date_parse_warning=date_parse_warning,
        parameters=parameters,
        next_position=next_position,
        rows=data_rows,
        db=db,
        raw_response_excerpt=text[:2048],
        format=Format.CSV,
    )
