"""JSONレスポンスパーサ。"""

from __future__ import annotations

import json
from typing import Any

from bojstat.enums import Format
from bojstat.normalize import normalize_key, parse_date_tolerant
from bojstat.types import ParsedResponse


def parse_json_response(text: str) -> ParsedResponse:
    """JSON本文を解析して共通形式へ変換する。

    Args:
        text: レスポンステキスト。

    Returns:
        解析結果。
    """

    payload: dict[str, Any] = json.loads(text)
    normalized_payload = {normalize_key(k): v for k, v in payload.items()}

    status = int(normalized_payload.get("STATUS", 0))
    message_id = str(normalized_payload.get("MESSAGEID", ""))
    message = str(normalized_payload.get("MESSAGE", ""))
    date_raw = (
        str(normalized_payload.get("DATE"))
        if normalized_payload.get("DATE") is not None
        else None
    )
    date_parsed, date_parse_warning = parse_date_tolerant(date_raw)

    parameters: dict[str, str | None] = {}
    parameter_obj = normalized_payload.get("PARAMETER")
    if isinstance(parameter_obj, dict):
        for key, value in parameter_obj.items():
            parameters[normalize_key(key)] = (
                str(value) if value not in (None, "") else None
            )

    next_position_value = normalized_payload.get("NEXTPOSITION")
    if next_position_value in (None, ""):
        next_position = None
    else:
        next_position = int(next_position_value)

    rows: list[dict[str, Any]] = []
    resultset = normalized_payload.get("RESULTSET")
    if isinstance(resultset, list):
        for row in resultset:
            if isinstance(row, dict):
                rows.append(row)

    db = normalized_payload.get("DB")
    db_value = str(db) if db is not None else None

    return ParsedResponse(
        status=status,
        message_id=message_id,
        message=message,
        date_raw=date_raw,
        date_parsed=date_parsed,
        date_parse_warning=date_parse_warning,
        parameters=parameters,
        next_position=next_position,
        rows=rows,
        db=db_value,
        raw_response_excerpt=text[:2048],
        format=Format.JSON,
    )
