from bojstat.types import MetadataRecord as MetadataRecord, TimeSeriesRecord as TimeSeriesRecord
from datetime import datetime
from typing import Any

def normalize_key(key: str) -> str:
    """キー名揺れを吸収して正規化する。"""
def parse_date_tolerant(raw: str | None) -> tuple[datetime | None, str | None]:
    """DATE文字列を寛容に解析する。

    Args:
        raw: DATE原文。

    Returns:
        (解析結果, 警告)。解析成功時は警告None。
    """
def frequency_code_from_label(label: str | None) -> tuple[str | None, str | None]:
    """頻度ラベルから頻度コードと週次アンカーを抽出する。"""
def expand_timeseries_rows(rows: list[dict[str, Any]], *, source_page_index: int, code_order_map: dict[str, int]) -> list[TimeSeriesRecord]:
    """正規化前行をTimeSeriesRecordへ展開する。"""
def normalize_metadata_rows(rows: list[dict[str, Any]]) -> list[MetadataRecord]:
    """正規化前行をMetadataRecordへ変換する。"""
