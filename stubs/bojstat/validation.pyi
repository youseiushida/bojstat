from bojstat.enums import Format as Format, Frequency as Frequency, Lang as Lang
from bojstat.errors import BojValidationError as BojValidationError
from collections.abc import Sequence
from typing import Any

def normalize_lang(value: Lang | str | None) -> Lang:
    """言語入力を正規化する。

    Args:
        value: 入力言語。

    Returns:
        正規化後の言語。

    Raises:
        BojValidationError: 値が不正な場合。
    """
def normalize_format(value: Format | str | None) -> Format:
    """出力形式入力を正規化する。"""
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
def normalize_db(value: str) -> str:
    """DB名を正規化する。"""
def validate_outbound_text(value: str, *, param_name: str) -> None:
    """外部送信する文字列を検証する。

    Args:
        value: 送信値。
        param_name: パラメータ名。

    Raises:
        BojValidationError: 禁止文字または全角文字を含む場合。
    """
def normalize_codes(code: str | Sequence[str]) -> list[str]:
    """系列コード入力を正規化する。"""
def normalize_layer(layer: str | Sequence[str | int]) -> list[str]:
    """階層指定を正規化する。"""
def normalize_periods(*, start: str | None, end: str | None, frequency: Frequency) -> tuple[str | None, str | None]:
    """開始期と終了期を正規化する。"""
def normalize_code_periods(*, start: str | None, end: str | None) -> tuple[str | None, str | None]:
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
def normalize_start_position(value: int | str | None) -> int | None:
    """検索開始位置を正規化する。"""
def validate_strict_auto_split(*, strict_api: bool, auto_split_codes: bool) -> None:
    """strict_api と auto_split_codes の契約を検証する。"""
def build_layer_params(layer: Sequence[str]) -> dict[str, str]:
    """LAYER指定から公式パラメータを作成する。"""
def normalize_raw_params(raw_params: dict[str, str] | None, *, allow_raw_override: bool) -> dict[str, str]:
    """raw_params の衝突検証を行う。"""
def guess_frequency_from_code(code: str) -> str:
    """系列コードから期種を推定する。

    Args:
        code: 系列コード。

    Returns:
        推定期種コード。推定不能時はUNKNOWN。
    """
def split_codes_by_frequency_and_size(codes: Sequence[str], *, chunk_size: int = 250) -> list[list[str]]:
    """系列コードを期種推定と件数で分割する。

    Args:
        codes: 系列コード列。
        chunk_size: チャンク上限。

    Returns:
        分割済みチャンク。
    """
def canonical_params(params: dict[str, Any]) -> list[tuple[str, str]]:
    """要求指紋生成向けにパラメータを正規化する。"""
