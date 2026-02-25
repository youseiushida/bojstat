"""返却モデル。"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from decimal import Decimal
from collections.abc import Callable
from typing import Any, Literal

from bojstat.enums import Frequency
from bojstat.types import MetadataRecord, ResponseMeta, TimeSeriesRecord

NumericMode = Literal["decimal", "float64", "string"]


def _convert_value(value: Decimal | None, mode: NumericMode) -> Decimal | float | str | None:
    if value is None:
        return None
    if mode == "decimal":
        return value
    if mode == "float64":
        return float(value)
    return format(value, "f")


def _record_to_dict(record: TimeSeriesRecord, mode: NumericMode = "decimal") -> dict[str, Any]:
    return {
        "series_code": record.series_code,
        "series_name": record.series_name,
        "unit": record.unit,
        "frequency": record.frequency,
        "frequency_code": record.frequency_code,
        "week_anchor": record.week_anchor,
        "category": record.category,
        "last_update": record.last_update,
        "survey_date": record.survey_date,
        "value": _convert_value(record.value, mode),
        "original_code_index": record.original_code_index,
        "source_page_index": record.source_page_index,
        "source_row_index": record.source_row_index,
        "extras": record.extras,
    }


def _metadata_to_dict(record: MetadataRecord) -> dict[str, Any]:
    return asdict(record)


def _meta_to_dict(meta: ResponseMeta) -> dict[str, Any]:
    payload = asdict(meta)
    date_parsed = payload.get("date_parsed")
    if date_parsed is not None:
        payload["date_parsed"] = date_parsed.isoformat()
    return payload


class TimeSeriesFrame:
    """時系列APIの返却オブジェクト。"""

    def __init__(self, records: list[TimeSeriesRecord], meta: ResponseMeta) -> None:
        self.records = records
        self.meta = meta

    def to_long(self, *, numeric_mode: NumericMode = "float64") -> list[dict[str, Any]]:
        """long形式データへ変換する。"""

        return [_record_to_dict(record, mode=numeric_mode) for record in self.records]

    def to_wide(self, *, numeric_mode: NumericMode = "float64") -> list[dict[str, Any]]:
        """wide形式へ変換する。"""

        table: dict[str, dict[str, Any]] = defaultdict(dict)
        for record in self.records:
            row = table[record.survey_date]
            row["survey_date"] = record.survey_date
            row[record.series_code] = _convert_value(record.value, numeric_mode)
        return [table[key] for key in sorted(table)]

    def to_pandas(self, *, numeric_mode: NumericMode = "float64") -> Any:
        """pandas.DataFrameへ変換する。"""

        try:
            import pandas as pd
        except ImportError as exc:
            raise RuntimeError("pandas が必要です。pip install 'bojstat[pandas]' を実行してください。") from exc
        return pd.DataFrame(self.to_long(numeric_mode=numeric_mode))

    def to_polars(self, *, numeric_mode: NumericMode = "float64") -> Any:
        """polars.DataFrameへ変換する。"""

        try:
            import polars as pl
        except ImportError as exc:
            raise RuntimeError("polars が必要です。pip install 'bojstat[polars]' を実行してください。") from exc
        return pl.DataFrame(self.to_long(numeric_mode=numeric_mode))

    def to_cache_payload(self) -> dict[str, Any]:
        """キャッシュ保存用dictに変換する。"""

        return {
            "records": [
                _record_to_dict(record, mode="string")
                for record in self.records
            ],
            "meta": _meta_to_dict(self.meta),
        }

    @classmethod
    def from_cache_payload(cls, payload: dict[str, Any]) -> "TimeSeriesFrame":
        """キャッシュdictから復元する。"""

        records: list[TimeSeriesRecord] = []
        for item in payload.get("records", []):
            value_raw = item.get("value")
            value = Decimal(value_raw) if value_raw not in (None, "") else None
            records.append(
                TimeSeriesRecord(
                    series_code=str(item.get("series_code", "")),
                    series_name=item.get("series_name"),
                    unit=item.get("unit"),
                    frequency=item.get("frequency"),
                    frequency_code=item.get("frequency_code"),
                    week_anchor=item.get("week_anchor"),
                    category=item.get("category"),
                    last_update=item.get("last_update"),
                    survey_date=str(item.get("survey_date", "")),
                    value=value,
                    original_code_index=item.get("original_code_index"),
                    source_page_index=int(item.get("source_page_index", 0)),
                    source_row_index=int(item.get("source_row_index", 0)),
                    extras=dict(item.get("extras") or {}),
                )
            )

        meta_dict = dict(payload.get("meta", {}))
        date_parsed = meta_dict.get("date_parsed")
        if isinstance(date_parsed, str) and date_parsed:
            from datetime import datetime

            try:
                meta_dict["date_parsed"] = datetime.fromisoformat(date_parsed)
            except ValueError:
                meta_dict["date_parsed"] = None
        meta = ResponseMeta(**meta_dict)
        return cls(records=records, meta=meta)


class MetadataFrame:
    """メタデータAPIの返却オブジェクト。"""

    def __init__(self, records: list[MetadataRecord], meta: ResponseMeta) -> None:
        self.records = records
        self.meta = meta

    def head(self, n: int) -> "MetadataFrame":
        """先頭n件を返す。"""

        return MetadataFrame(records=self.records[:n], meta=self.meta)

    @property
    def series_codes(self) -> list[str]:
        """系列コード一覧を返す。"""

        return [record.series_code for record in self.records if record.series_code]

    def find(
        self,
        *,
        name_contains: str | None = None,
        frequency: Frequency | str | None = None,
    ) -> "MetadataFrame":
        """簡易検索で絞り込む。"""

        result = self.records
        if name_contains:
            needle = name_contains.casefold()
            result = [
                record
                for record in result
                if record.series_name and needle in record.series_name.casefold()
            ]
        if frequency is not None:
            freq_text = frequency.value if isinstance(frequency, Frequency) else str(frequency)
            freq_text = freq_text.upper()
            result = [
                record
                for record in result
                if record.frequency and freq_text in record.frequency.upper()
            ]
        return MetadataFrame(records=result, meta=self.meta)

    def filter(self, predicate: Callable[[MetadataRecord], bool]) -> "MetadataFrame":
        """条件関数でレコードを絞り込む。

        Args:
            predicate: MetadataRecordを受け取りboolを返す関数。
                Trueを返したレコードのみが結果に含まれる。

        Returns:
            条件を満たすレコードだけを含む新しいMetadataFrame。

        Examples:
            >>> frame.filter(lambda r: r.category == "外国為替市況")
            >>> frame.filter(lambda r: r.layer1 == "1" and r.unit == "億円")
        """
        return MetadataFrame(
            records=[r for r in self.records if predicate(r)],
            meta=self.meta,
        )

    def to_pandas(self) -> Any:
        """pandas.DataFrameへ変換する。"""

        try:
            import pandas as pd
        except ImportError as exc:
            raise RuntimeError("pandas が必要です。pip install 'bojstat[pandas]' を実行してください。") from exc
        return pd.DataFrame([_metadata_to_dict(record) for record in self.records])

    def to_polars(self) -> Any:
        """polars.DataFrameへ変換する。"""

        try:
            import polars as pl
        except ImportError as exc:
            raise RuntimeError("polars が必要です。pip install 'bojstat[polars]' を実行してください。") from exc
        return pl.DataFrame([_metadata_to_dict(record) for record in self.records])

    def to_cache_payload(self) -> dict[str, Any]:
        """キャッシュ保存用dictに変換する。"""

        return {
            "records": [_metadata_to_dict(record) for record in self.records],
            "meta": _meta_to_dict(self.meta),
        }

    @classmethod
    def from_cache_payload(cls, payload: dict[str, Any]) -> "MetadataFrame":
        """キャッシュdictから復元する。"""

        records = [MetadataRecord(**item) for item in payload.get("records", [])]
        meta_dict = dict(payload.get("meta", {}))
        date_parsed = meta_dict.get("date_parsed")
        if isinstance(date_parsed, str) and date_parsed:
            from datetime import datetime

            try:
                meta_dict["date_parsed"] = datetime.fromisoformat(date_parsed)
            except ValueError:
                meta_dict["date_parsed"] = None
        meta = ResponseMeta(**meta_dict)
        return cls(records=records, meta=meta)
