"""validation モジュールのテスト。"""

from __future__ import annotations

import pytest

from bojstat.errors import BojValidationError
from bojstat.validation import (
    normalize_code_periods,
    normalize_lang,
    split_codes_by_frequency_and_size,
    validate_outbound_text,
    validate_strict_auto_split,
)


def test_normalize_lang_case_insensitive() -> None:
    assert normalize_lang("jp").value == "JP"
    assert normalize_lang("En").value == "EN"


def test_validate_outbound_text_rejects_full_width() -> None:
    with pytest.raises(BojValidationError):
        validate_outbound_text("テスト", param_name="DB")


def test_validate_strict_auto_split_conflict() -> None:
    with pytest.raises(ValueError):
        validate_strict_auto_split(strict_api=True, auto_split_codes=True)


def test_split_codes_by_frequency_and_size() -> None:
    codes = [f"CODE{i}@D" for i in range(300)]
    chunks = split_codes_by_frequency_and_size(codes)
    assert len(chunks) == 2
    assert len(chunks[0]) == 250
    assert len(chunks[1]) == 50


def test_normalize_code_periods_accepts_year_and_month() -> None:
    start, end = normalize_code_periods(start="2024", end="202412")
    assert start == "2024"
    assert end == "202412"


def test_normalize_code_periods_rejects_invalid_format() -> None:
    with pytest.raises(BojValidationError):
        normalize_code_periods(start="20240101", end=None)


def test_normalize_code_periods_rejects_order_inversion() -> None:
    with pytest.raises(BojValidationError):
        normalize_code_periods(start="202412", end="2024")
