from _typeshed import Incomplete
from bojstat.enums import Frequency as Frequency
from bojstat.types import MetadataRecord as MetadataRecord, ResponseMeta as ResponseMeta, TimeSeriesRecord as TimeSeriesRecord
from collections.abc import Callable as Callable
from typing import Any

NumericMode: Incomplete

class TimeSeriesFrame:
    """時系列APIの返却オブジェクト。"""
    records: Incomplete
    meta: Incomplete
    def __init__(self, records: list[TimeSeriesRecord], meta: ResponseMeta) -> None: ...
    def to_long(self, *, numeric_mode: NumericMode = 'float64') -> list[dict[str, Any]]:
        """long形式データへ変換する。"""
    def to_wide(self, *, numeric_mode: NumericMode = 'float64') -> list[dict[str, Any]]:
        """wide形式へ変換する。"""
    def to_pandas(self, *, numeric_mode: NumericMode = 'float64') -> Any:
        """pandas.DataFrameへ変換する。"""
    def to_polars(self, *, numeric_mode: NumericMode = 'float64') -> Any:
        """polars.DataFrameへ変換する。"""
    def to_cache_payload(self) -> dict[str, Any]:
        """キャッシュ保存用dictに変換する。"""
    @classmethod
    def from_cache_payload(cls, payload: dict[str, Any]) -> TimeSeriesFrame:
        """キャッシュdictから復元する。"""

class MetadataFrame:
    """メタデータAPIの返却オブジェクト。"""
    records: Incomplete
    meta: Incomplete
    def __init__(self, records: list[MetadataRecord], meta: ResponseMeta) -> None: ...
    def head(self, n: int) -> MetadataFrame:
        """先頭n件を返す。"""
    @property
    def series_codes(self) -> list[str]:
        """系列コード一覧を返す。"""
    def find(self, *, name_contains: str | None = None, frequency: Frequency | str | None = None) -> MetadataFrame:
        """簡易検索で絞り込む。"""
    def filter(self, predicate: Callable[[MetadataRecord], bool]) -> MetadataFrame:
        '''条件関数でレコードを絞り込む。

        Args:
            predicate: MetadataRecordを受け取りboolを返す関数。
                Trueを返したレコードのみが結果に含まれる。

        Returns:
            条件を満たすレコードだけを含む新しいMetadataFrame。

        Examples:
            >>> frame.filter(lambda r: r.category == "外国為替市況")
            >>> frame.filter(lambda r: r.layer1 == "1" and r.unit == "億円")
        '''
    def to_pandas(self) -> Any:
        """pandas.DataFrameへ変換する。"""
    def to_polars(self) -> Any:
        """polars.DataFrameへ変換する。"""
    def to_cache_payload(self) -> dict[str, Any]:
        """キャッシュ保存用dictに変換する。"""
    @classmethod
    def from_cache_payload(cls, payload: dict[str, Any]) -> MetadataFrame:
        """キャッシュdictから復元する。"""
