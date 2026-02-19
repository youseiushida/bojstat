"""db_catalog モジュールのテスト。"""

from __future__ import annotations

from bojstat.db_catalog import DB_CATALOG, DBInfo, get_db_info, is_known_db, list_dbs
from bojstat.enums import DB


def test_db_enum_count() -> None:
    assert len(DB) == 50


def test_db_enum_is_strenum() -> None:
    assert DB.CO == "CO"
    assert DB.FM08 == "FM08"
    assert str(DB.IR01) == "IR01"


def test_catalog_count_matches_enum() -> None:
    assert len(DB_CATALOG) == 50
    assert len(DB_CATALOG) == len(DB)


def test_list_dbs_all() -> None:
    all_dbs = list_dbs()
    assert len(all_dbs) == 50
    assert all(isinstance(info, DBInfo) for info in all_dbs)


def test_list_dbs_filter_by_category() -> None:
    price_dbs = list_dbs(category="物価")
    assert len(price_dbs) == 4
    codes = {info.code for info in price_dbs}
    assert codes == {"PR01", "PR02", "PR03", "PR04"}


def test_list_dbs_filter_partial_match() -> None:
    interest_dbs = list_dbs(category="金利")
    assert len(interest_dbs) == 4
    codes = {info.code for info in interest_dbs}
    assert codes == {"IR01", "IR02", "IR03", "IR04"}


def test_list_dbs_filter_no_match() -> None:
    result = list_dbs(category="存在しないカテゴリ")
    assert result == []


def test_get_db_info_known() -> None:
    info = get_db_info("CO")
    assert info is not None
    assert info.code == "CO"
    assert info.name_ja == "短観"
    assert info.category_ja == "短観"


def test_get_db_info_case_insensitive() -> None:
    info = get_db_info("co")
    assert info is not None
    assert info.code == "CO"

    info2 = get_db_info("fm08")
    assert info2 is not None
    assert info2.code == "FM08"


def test_get_db_info_unknown() -> None:
    assert get_db_info("ZZZZ") is None


def test_is_known_db_true() -> None:
    assert is_known_db("CO") is True
    assert is_known_db("fm08") is True
    assert is_known_db("FF") is True


def test_is_known_db_false() -> None:
    assert is_known_db("ZZZZ") is False
    assert is_known_db("") is False


def test_dbinfo_str() -> None:
    info = get_db_info("CO")
    assert info is not None
    assert str(info) == "CO: 短観"
