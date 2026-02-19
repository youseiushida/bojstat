"""入力正規化と送信前バリデーション。"""

from __future__ import annotations

import re
import unicodedata
import warnings
from collections.abc import Iterable, Sequence
from typing import Any

from bojstat.db_catalog import is_known_db
from bojstat.enums import Format, Frequency, Lang
from bojstat.errors import BojValidationError

_FORBIDDEN_CHARS = {'<', '>', '"', '!', '|', '\\', '¥', ';', "'"}
_CORE_PARAM_KEYS = {
    "DB",
    "CODE",
    "LAYER",
    "FREQUENCY",
    "STARTDATE",
    "ENDDATE",
    "STARTPOSITION",
    "LANG",
    "FORMAT",
}
_CODE_API_PERIOD_PATTERN = re.compile(r"^\d{4}(\d{2})?$")


def normalize_lang(value: Lang | str | None) -> Lang:
    """言語入力を正規化する。

    Args:
        value: 入力言語。

    Returns:
        正規化後の言語。

    Raises:
        BojValidationError: 値が不正な場合。
    """

    if value is None:
        return Lang.JP
    if isinstance(value, Lang):
        return value
    normalized = str(value).strip().upper()
    try:
        return Lang(normalized)
    except ValueError as exc:
        raise BojValidationError("LANG が不正です。", validation_code="invalid_lang") from exc


def normalize_format(value: Format | str | None) -> Format:
    """出力形式入力を正規化する。"""

    if value is None:
        return Format.JSON
    if isinstance(value, Format):
        return value
    normalized = str(value).strip().upper()
    try:
        return Format(normalized)
    except ValueError as exc:
        raise BojValidationError(
            "FORMAT が不正です。", validation_code="invalid_format"
        ) from exc


def normalize_frequency(value: Frequency | str | None, *, required: bool) -> Frequency | None:
    """期種入力を正規化する。

    Args:
        value: 期種入力。
        required: 必須項目か。

    Returns:
        正規化済み期種。任意項目未指定時はNone。

    Raises:
        BojValidationError: 必須未指定または不正値。
    """

    if value is None:
        if required:
            raise BojValidationError(
                "FREQUENCY が指定されていません。",
                validation_code="missing_frequency",
            )
        return None
    if isinstance(value, Frequency):
        return value
    normalized = str(value).strip().upper()
    try:
        return Frequency(normalized)
    except ValueError as exc:
        raise BojValidationError(
            "FREQUENCY が不正です。", validation_code="invalid_frequency"
        ) from exc


def normalize_db(value: str) -> str:
    """DB名を正規化する。"""

    db = value.strip().upper()
    if not db:
        raise BojValidationError("DB が指定されていません。", validation_code="missing_db")
    validate_outbound_text(db, param_name="DB")
    if not is_known_db(db):
        warnings.warn(
            f"DB '{db}' は既知のDBコード一覧に含まれていません。"
            " 新規追加されたDBの可能性があります。",
            stacklevel=2,
        )
    return db


def _contains_full_width(text: str) -> bool:
    for ch in text:
        if unicodedata.east_asian_width(ch) in {"W", "F"}:
            return True
    return False


def validate_outbound_text(value: str, *, param_name: str) -> None:
    """外部送信する文字列を検証する。

    Args:
        value: 送信値。
        param_name: パラメータ名。

    Raises:
        BojValidationError: 禁止文字または全角文字を含む場合。
    """

    if any(ch in _FORBIDDEN_CHARS for ch in value):
        raise BojValidationError(
            f"{param_name} に禁止文字が含まれています。",
            validation_code="forbidden_character",
        )
    if _contains_full_width(value):
        raise BojValidationError(
            f"{param_name} に全角文字は指定できません。",
            validation_code="full_width_not_allowed",
        )


def normalize_codes(code: str | Sequence[str]) -> list[str]:
    """系列コード入力を正規化する。"""

    if isinstance(code, str):
        values = [chunk.strip() for chunk in code.split(",")]
    else:
        values = [str(chunk).strip() for chunk in code]

    codes = [value for value in values if value]
    if not codes:
        raise BojValidationError(
            "CODE が指定されていません。", validation_code="missing_code"
        )
    for item in codes:
        validate_outbound_text(item, param_name="CODE")
    return codes


def normalize_layer(layer: str | Sequence[str | int]) -> list[str]:
    """階層指定を正規化する。"""

    values: list[str]
    if isinstance(layer, str):
        values = [chunk.strip() for chunk in layer.split(",")]
    else:
        values = [str(chunk).strip() for chunk in layer]
    values = [v for v in values if v]
    if not values:
        raise BojValidationError(
            "LAYER が指定されていません。", validation_code="missing_layer"
        )
    if len(values) > 5:
        raise BojValidationError(
            "LAYER は最大5階層です。", validation_code="too_many_layers"
        )
    if values[0] == "*":
        pass
    elif not values[0].isdigit():
        raise BojValidationError(
            "LAYER1 は数値または*で指定してください。",
            validation_code="invalid_layer1",
        )
    for index, item in enumerate(values, start=1):
        if item != "*" and not item.isdigit():
            raise BojValidationError(
                f"LAYER{index} が不正です。", validation_code="invalid_layer"
            )
        validate_outbound_text(item, param_name=f"LAYER{index}")
    return values


def _validate_period_format(period: str, *, frequency: Frequency) -> None:
    if frequency in {Frequency.CY, Frequency.FY}:
        pattern = r"^\d{4}$"
    elif frequency in {Frequency.CH, Frequency.FH, Frequency.Q}:
        pattern = r"^\d{6}$"
    else:
        pattern = r"^\d{6}$"
    if not re.match(pattern, period):
        raise BojValidationError(
            f"{frequency.value} 用の時期形式が不正です: {period}",
            validation_code="invalid_period_format",
        )
    year = int(period[:4])
    if year < 1850 or year > 2050:
        raise BojValidationError(
            "時期は1850年から2050年までです。", validation_code="period_out_of_range"
        )
    if len(period) == 6 and frequency in {Frequency.CH, Frequency.FH}:
        if period[4:6] not in {"01", "02"}:
            raise BojValidationError(
                "半期指定は01または02です。", validation_code="invalid_half"
            )
    if len(period) == 6 and frequency == Frequency.Q:
        if period[4:6] not in {"01", "02", "03", "04"}:
            raise BojValidationError(
                "四半期指定は01-04です。", validation_code="invalid_quarter"
            )
    if len(period) == 6 and frequency in {Frequency.M, Frequency.W, Frequency.D}:
        month = int(period[4:6])
        if month < 1 or month > 12:
            raise BojValidationError(
                "月指定は01-12です。", validation_code="invalid_month"
            )


def _period_key(period: str) -> tuple[int, int]:
    year = int(period[:4])
    suffix = int(period[4:6]) if len(period) == 6 else 0
    return (year, suffix)


def normalize_periods(
    *,
    start: str | None,
    end: str | None,
    frequency: Frequency,
) -> tuple[str | None, str | None]:
    """開始期と終了期を正規化する。"""

    start_norm = start.strip() if start is not None else None
    end_norm = end.strip() if end is not None else None
    if start_norm:
        validate_outbound_text(start_norm, param_name="STARTDATE")
        _validate_period_format(start_norm, frequency=frequency)
    if end_norm:
        validate_outbound_text(end_norm, param_name="ENDDATE")
        _validate_period_format(end_norm, frequency=frequency)
    if start_norm and end_norm and _period_key(start_norm) > _period_key(end_norm):
        raise BojValidationError(
            "開始期と終了期の順序が不正です。", validation_code="period_order"
        )
    return start_norm, end_norm


def _validate_code_api_period_format(period: str, *, param_name: str) -> None:
    """Code API の時期形式を検証する。

    Args:
        period: 検証対象の時期。
        param_name: パラメータ名。

    Raises:
        BojValidationError: 形式または範囲が不正な場合。
    """

    if not _CODE_API_PERIOD_PATTERN.match(period):
        raise BojValidationError(
            f"{param_name} はYYYYまたはYYYYMM形式で指定してください。",
            validation_code="invalid_code_period_format",
        )
    year = int(period[:4])
    if year < 1850 or year > 2050:
        raise BojValidationError(
            "時期は1850年から2050年までです。",
            validation_code="period_out_of_range",
        )
    if len(period) == 6:
        month = int(period[4:6])
        if month < 1 or month > 12:
            raise BojValidationError(
                "月指定は01-12です。",
                validation_code="invalid_month",
            )


def normalize_code_periods(
    *,
    start: str | None,
    end: str | None,
) -> tuple[str | None, str | None]:
    """Code API の開始期・終了期を正規化する。

    Code API は系列期種に依存して時期形式が変わるため、クライアント側では
    `YYYY` または `YYYYMM` の軽量検証と順序検証のみを行い、期種整合は API 応答へ委譲する。

    Args:
        start: 開始期。
        end: 終了期。

    Returns:
        正規化後の開始期・終了期。

    Raises:
        BojValidationError: 入力形式または順序が不正な場合。
    """

    start_norm = start.strip() if start is not None else None
    end_norm = end.strip() if end is not None else None
    if start_norm:
        validate_outbound_text(start_norm, param_name="STARTDATE")
        _validate_code_api_period_format(start_norm, param_name="STARTDATE")
    if end_norm:
        validate_outbound_text(end_norm, param_name="ENDDATE")
        _validate_code_api_period_format(end_norm, param_name="ENDDATE")
    if start_norm and end_norm and _period_key(start_norm) > _period_key(end_norm):
        raise BojValidationError(
            "開始期と終了期の順序が不正です。",
            validation_code="period_order",
        )
    return start_norm, end_norm


def normalize_start_position(value: int | str | None) -> int | None:
    """検索開始位置を正規化する。"""

    if value is None:
        return None
    if isinstance(value, str):
        raw = value.strip()
        if not raw.isdigit():
            raise BojValidationError(
                "STARTPOSITION は1以上の整数です。",
                validation_code="invalid_start_position",
            )
        parsed = int(raw)
    else:
        parsed = int(value)
    if parsed < 1:
        raise BojValidationError(
            "STARTPOSITION は1以上の整数です。",
            validation_code="invalid_start_position",
        )
    return parsed


def validate_strict_auto_split(*, strict_api: bool, auto_split_codes: bool) -> None:
    """strict_api と auto_split_codes の契約を検証する。"""

    if strict_api and auto_split_codes:
        raise ValueError("strict_api=True と auto_split_codes=True は同時指定不可")



def normalize_raw_params(
    raw_params: dict[str, str] | None,
    *,
    allow_raw_override: bool,
) -> dict[str, str]:
    """raw_params の衝突検証を行う。"""

    if not raw_params:
        return {}
    normalized: dict[str, str] = {}
    for key, value in raw_params.items():
        normalized_key = key.strip().upper()
        if not normalized_key:
            continue
        if normalized_key in _CORE_PARAM_KEYS:
            raise BojValidationError(
                f"{normalized_key} は raw_params で上書きできません。",
                validation_code="raw_override_core_forbidden",
            )
        normalized[normalized_key] = str(value)
    if not allow_raw_override:
        return normalized
    return normalized


def guess_frequency_from_code(code: str) -> str:
    """系列コードから期種を推定する。

    Args:
        code: 系列コード。

    Returns:
        推定期種コード。推定不能時はUNKNOWN。
    """

    if "@" in code and code.rsplit("@", 1)[-1]:
        suffix = code.rsplit("@", 1)[-1].upper()
        if suffix in {"D", "W", "W0", "W1", "W2", "W3", "W4", "W5", "W6", "M", "Q"}:
            return "W" if suffix.startswith("W") else suffix
    match = re.search(r"([CYFHQMWD]{1,2})\d{2,}$", code.upper())
    if match:
        freq = match.group(1)
        if freq in {"CY", "FY", "CH", "FH", "Q", "M", "W", "D"}:
            return freq
    return "UNKNOWN"


def split_codes_by_frequency_and_size(
    codes: Sequence[str], *, chunk_size: int = 250
) -> list[list[str]]:
    """系列コードを期種推定と件数で分割する。

    Args:
        codes: 系列コード列。
        chunk_size: チャンク上限。

    Returns:
        分割済みチャンク。
    """

    grouped: dict[str, list[str]] = {}
    order: list[str] = []
    for code in codes:
        key = guess_frequency_from_code(code)
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(code)

    chunks: list[list[str]] = []
    for key in order:
        items = grouped[key]
        for idx in range(0, len(items), chunk_size):
            chunks.append(items[idx : idx + chunk_size])
    return chunks


def canonical_params(params: dict[str, Any]) -> list[tuple[str, str]]:
    """要求指紋生成向けにパラメータを正規化する。"""

    normalized: list[tuple[str, str]] = []
    for key in sorted(params):
        value = params[key]
        if value is None:
            continue
        if isinstance(value, Iterable) and not isinstance(value, (str, bytes, bytearray)):
            rendered = ",".join(str(item) for item in value)
        else:
            rendered = str(value)
        normalized.append((key.upper(), rendered))
    return normalized
