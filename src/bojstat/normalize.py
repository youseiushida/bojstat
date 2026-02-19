"""レスポンス正規化処理。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from bojstat.types import MetadataRecord, TimeSeriesRecord

_KEY_ALIASES = {
    "SERIESCODE": "SERIES_CODE",
    "SERIES CODE": "SERIES_CODE",
    "NAMEOFTIMESERIESJ": "NAME_OF_TIME_SERIES_J",
    "NAME OF TIME SERIES J": "NAME_OF_TIME_SERIES_J",
    "NAMEOFTIMESERIES": "NAME_OF_TIME_SERIES",
    "NAME OF TIME SERIES": "NAME_OF_TIME_SERIES",
    "UNITJ": "UNIT_J",
    "UNIT J": "UNIT_J",
    "CATEGORYJ": "CATEGORY_J",
    "CATEGORY J": "CATEGORY_J",
    "LASTUPDATE": "LAST_UPDATE",
    "LAST UPDATE": "LAST_UPDATE",
    "SURVEYDATES": "SURVEY_DATES",
    "SURVEY DATES": "SURVEY_DATES",
    "STARTOFTHETIMESERIES": "START_OF_THE_TIME_SERIES",
    "ENDOFTHETIMESERIES": "END_OF_THE_TIME_SERIES",
    "NOTESJ": "NOTES_J",
}


def normalize_key(key: str) -> str:
    """キー名揺れを吸収して正規化する。"""

    compact = key.strip().replace("_", " ").upper()
    compact_no_space = compact.replace(" ", "")
    if compact_no_space in _KEY_ALIASES:
        return _KEY_ALIASES[compact_no_space]
    if compact in _KEY_ALIASES:
        return _KEY_ALIASES[compact]
    return compact.replace(" ", "_")


def parse_date_tolerant(raw: str | None) -> tuple[datetime | None, str | None]:
    """DATE文字列を寛容に解析する。

    Args:
        raw: DATE原文。

    Returns:
        (解析結果, 警告)。解析成功時は警告None。
    """

    if not raw:
        return None, None
    text = raw.strip()
    candidates = [text]
    if "Z+" in text:
        candidates.append(text.replace("Z+", "+"))
    if text.endswith("Z"):
        candidates.append(text[:-1] + "+00:00")
    for candidate in candidates:
        try:
            return datetime.fromisoformat(candidate), None
        except ValueError:
            continue
    return None, f"DATEの解析に失敗しました: {raw}"


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "null":
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def frequency_code_from_label(label: str | None) -> tuple[str | None, str | None]:
    """頻度ラベルから頻度コードと週次アンカーを抽出する。"""

    if not label:
        return None, None
    normalized = label.upper()
    if "ANNUAL (MAR)" in normalized:
        return "FY", None
    if "ANNUAL" in normalized:
        return "CY", None
    if "SEMIANNUAL (SEP)" in normalized:
        return "FH", None
    if "SEMIANNUAL" in normalized:
        return "CH", None
    if "QUARTERLY" in normalized:
        return "Q", None
    if "MONTHLY" in normalized:
        return "M", None
    if "DAILY" in normalized:
        return "D", None
    if "WEEKLY" in normalized:
        week_anchor = None
        if "(" in normalized and ")" in normalized:
            week_anchor = normalized.split("(", 1)[1].split(")", 1)[0]
        return "W", week_anchor
    return None, None


def _extract(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row:
            return row[key]
    return None


def expand_timeseries_rows(
    rows: list[dict[str, Any]],
    *,
    source_page_index: int,
    code_order_map: dict[str, int],
) -> list[TimeSeriesRecord]:
    """正規化前行をTimeSeriesRecordへ展開する。"""

    result: list[TimeSeriesRecord] = []
    for row_index, raw in enumerate(rows):
        normalized = {normalize_key(k): v for k, v in raw.items()}
        series_code = str(_extract(normalized, "SERIES_CODE") or "").strip()
        if not series_code:
            continue
        series_name = _extract(normalized, "NAME_OF_TIME_SERIES_J", "NAME_OF_TIME_SERIES")
        unit = _extract(normalized, "UNIT_J", "UNIT")
        frequency = _extract(normalized, "FREQUENCY")
        category = _extract(normalized, "CATEGORY_J", "CATEGORY")
        last_update = _extract(normalized, "LAST_UPDATE")
        freq_code, week_anchor = frequency_code_from_label(str(frequency) if frequency else None)
        values_field = _extract(normalized, "VALUES")
        original_index = code_order_map.get(series_code)

        if isinstance(values_field, dict):
            nested = {normalize_key(k): v for k, v in values_field.items()}
            nested_dates = list(nested.get("SURVEY_DATES", []))
            nested_values = list(nested.get("VALUES", []))
            for idx, survey in enumerate(nested_dates):
                value = nested_values[idx] if idx < len(nested_values) else None
                result.append(
                    TimeSeriesRecord(
                        series_code=series_code,
                        series_name=str(series_name) if series_name is not None else None,
                        unit=str(unit) if unit is not None else None,
                        frequency=str(frequency) if frequency is not None else None,
                        frequency_code=freq_code,
                        week_anchor=week_anchor,
                        category=str(category) if category is not None else None,
                        last_update=str(last_update) if last_update is not None else None,
                        survey_date=str(survey),
                        value=_decimal_or_none(value),
                        original_code_index=original_index,
                        source_page_index=source_page_index,
                        source_row_index=row_index,
                        extras={
                            key: val
                            for key, val in normalized.items()
                            if key
                            not in {
                                "SERIES_CODE",
                                "NAME_OF_TIME_SERIES_J",
                                "NAME_OF_TIME_SERIES",
                                "UNIT_J",
                                "UNIT",
                                "FREQUENCY",
                                "CATEGORY_J",
                                "CATEGORY",
                                "LAST_UPDATE",
                                "VALUES",
                            }
                        },
                    )
                )
            continue

        survey_value = _extract(normalized, "SURVEY_DATES")
        value = _extract(normalized, "VALUES")
        if survey_value is None:
            continue
        result.append(
            TimeSeriesRecord(
                series_code=series_code,
                series_name=str(series_name) if series_name is not None else None,
                unit=str(unit) if unit is not None else None,
                frequency=str(frequency) if frequency is not None else None,
                frequency_code=freq_code,
                week_anchor=week_anchor,
                category=str(category) if category is not None else None,
                last_update=str(last_update) if last_update is not None else None,
                survey_date=str(survey_value),
                value=_decimal_or_none(value),
                original_code_index=original_index,
                source_page_index=source_page_index,
                source_row_index=row_index,
                extras={
                    key: val
                    for key, val in normalized.items()
                    if key
                    not in {
                        "SERIES_CODE",
                        "NAME_OF_TIME_SERIES_J",
                        "NAME_OF_TIME_SERIES",
                        "UNIT_J",
                        "UNIT",
                        "FREQUENCY",
                        "CATEGORY_J",
                        "CATEGORY",
                        "LAST_UPDATE",
                        "SURVEY_DATES",
                        "VALUES",
                    }
                },
            )
        )
    return result


def normalize_metadata_rows(rows: list[dict[str, Any]]) -> list[MetadataRecord]:
    """正規化前行をMetadataRecordへ変換する。"""

    result: list[MetadataRecord] = []
    for raw in rows:
        normalized = {normalize_key(k): v for k, v in raw.items()}
        record = MetadataRecord(
            series_code=str(_extract(normalized, "SERIES_CODE") or "").strip(),
            series_name=(
                str(_extract(normalized, "NAME_OF_TIME_SERIES_J", "NAME_OF_TIME_SERIES"))
                if _extract(normalized, "NAME_OF_TIME_SERIES_J", "NAME_OF_TIME_SERIES")
                is not None
                else None
            ),
            unit=(
                str(_extract(normalized, "UNIT_J", "UNIT"))
                if _extract(normalized, "UNIT_J", "UNIT") is not None
                else None
            ),
            frequency=(
                str(_extract(normalized, "FREQUENCY"))
                if _extract(normalized, "FREQUENCY") is not None
                else None
            ),
            category=(
                str(_extract(normalized, "CATEGORY_J", "CATEGORY"))
                if _extract(normalized, "CATEGORY_J", "CATEGORY") is not None
                else None
            ),
            layer1=(
                str(_extract(normalized, "LAYER1"))
                if _extract(normalized, "LAYER1") is not None
                else None
            ),
            layer2=(
                str(_extract(normalized, "LAYER2"))
                if _extract(normalized, "LAYER2") is not None
                else None
            ),
            layer3=(
                str(_extract(normalized, "LAYER3"))
                if _extract(normalized, "LAYER3") is not None
                else None
            ),
            layer4=(
                str(_extract(normalized, "LAYER4"))
                if _extract(normalized, "LAYER4") is not None
                else None
            ),
            layer5=(
                str(_extract(normalized, "LAYER5"))
                if _extract(normalized, "LAYER5") is not None
                else None
            ),
            start_of_time_series=(
                str(_extract(normalized, "START_OF_THE_TIME_SERIES"))
                if _extract(normalized, "START_OF_THE_TIME_SERIES") is not None
                else None
            ),
            end_of_time_series=(
                str(_extract(normalized, "END_OF_THE_TIME_SERIES"))
                if _extract(normalized, "END_OF_THE_TIME_SERIES") is not None
                else None
            ),
            last_update=(
                str(_extract(normalized, "LAST_UPDATE"))
                if _extract(normalized, "LAST_UPDATE") is not None
                else None
            ),
            notes=(
                str(_extract(normalized, "NOTES_J", "NOTES"))
                if _extract(normalized, "NOTES_J", "NOTES") is not None
                else None
            ),
            extras={
                key: val
                for key, val in normalized.items()
                if key
                not in {
                    "SERIES_CODE",
                    "NAME_OF_TIME_SERIES_J",
                    "NAME_OF_TIME_SERIES",
                    "UNIT_J",
                    "UNIT",
                    "FREQUENCY",
                    "CATEGORY_J",
                    "CATEGORY",
                    "LAYER1",
                    "LAYER2",
                    "LAYER3",
                    "LAYER4",
                    "LAYER5",
                    "START_OF_THE_TIME_SERIES",
                    "END_OF_THE_TIME_SERIES",
                    "LAST_UPDATE",
                    "NOTES_J",
                    "NOTES",
                }
            },
        )
        result.append(record)
    return result
