"""CLI出力処理のテスト。"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Any

from bojstat.cli import _dump_frame
from bojstat.models import MetadataFrame
from bojstat.types import MetadataRecord, ResponseMeta


def _make_meta() -> ResponseMeta:
    return ResponseMeta(
        status=200,
        message_id="M000",
        message="ok",
        date_raw="20250226",
        date_parsed=datetime(2025, 2, 26, 10, 20, 30),
        date_parse_warning=None,
        date_semantics="response_generated_at",
        next_position=None,
        parameters={},
        request_url="https://example.invalid/api",
        schema_version="1.0.0",
        parser_version="1.0.0",
        normalizer_version="1.0.0",
    )


def test_dump_frame_json_uses_cache_payload_for_slots_meta(tmp_path: Path) -> None:
    frame = MetadataFrame(
        records=[
            MetadataRecord(
                series_code="FXERD01",
                series_name="series",
                unit="yen",
                frequency="MONTHLY",
                category="cat",
                layer1="1",
                layer2=None,
                layer3=None,
                layer4=None,
                layer5=None,
                start_of_time_series="202001",
                end_of_time_series="202502",
                last_update="20250226",
                notes=None,
                extras={"note": "x"},
            )
        ],
        meta=_make_meta(),
    )
    out = tmp_path / "meta.json"

    _dump_frame(frame, out)

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["meta"]["status"] == 200
    assert payload["meta"]["date_parsed"] == "2025-02-26T10:20:30"
    assert payload["records"][0]["series_code"] == "FXERD01"
    assert payload["records"][0]["extras"] == {"note": "x"}


class _FakeDataFrame:
    def __init__(self) -> None:
        self._data: dict[str, list[Any]] = {
            "series_code": ["S1"],
            "extras": [{"a": 1}],
            "tags": [["x", "y"]],
            "value": [1.0],
        }
        self.saved: tuple[Path, bool] | None = None

    @property
    def columns(self) -> list[str]:
        return list(self._data.keys())

    def __getitem__(self, key: str) -> list[Any]:
        return self._data[key]

    def __setitem__(self, key: str, value: list[Any]) -> None:
        self._data[key] = list(value)

    def to_parquet(self, out: Path, index: bool = False) -> None:
        self.saved = (out, index)


class _FakeFrame:
    def __init__(self, df: _FakeDataFrame) -> None:
        self._df = df

    def to_pandas(self) -> _FakeDataFrame:
        return self._df


def test_dump_frame_parquet_stringifies_nested_cells(tmp_path: Path, monkeypatch: Any) -> None:
    fake_pyarrow = ModuleType("pyarrow")
    monkeypatch.setitem(sys.modules, "pyarrow", fake_pyarrow)

    df = _FakeDataFrame()
    frame = _FakeFrame(df)
    out = tmp_path / "data.parquet"

    _dump_frame(frame, out)

    assert df.saved == (out, False)
    assert isinstance(df._data["extras"][0], str)
    assert isinstance(df._data["tags"][0], str)
    assert json.loads(df._data["extras"][0]) == {"a": 1}
    assert json.loads(df._data["tags"][0]) == ["x", "y"]
    assert df._data["value"][0] == 1.0
