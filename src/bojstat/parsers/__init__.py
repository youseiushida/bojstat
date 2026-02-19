"""レスポンスパーサ公開API。"""

from __future__ import annotations

from bojstat.enums import Format, Lang
from bojstat.parsers.csv_parser import parse_csv_response
from bojstat.parsers.json_parser import parse_json_response
from bojstat.types import ParsedResponse


def decode_response_bytes(payload: bytes, *, lang: Lang) -> str:
    """バイト列を言語規約に従ってデコードする。

    Args:
        payload: レスポンスバイト列。
        lang: 指定言語。

    Returns:
        デコード済み文字列。
    """

    if lang == Lang.JP:
        try:
            return payload.decode("shift_jis")
        except UnicodeDecodeError:
            return payload.decode("utf-8", errors="replace")
    return payload.decode("utf-8", errors="replace")


def parse_response(
    payload: bytes,
    *,
    requested_format: Format,
    lang: Lang,
) -> ParsedResponse:
    """レスポンスをJSON/CSV自動判定で解析する。

    Args:
        payload: レスポンスバイト列。
        requested_format: 要求形式。
        lang: 要求言語。

    Returns:
        解析結果。
    """

    utf8_text = payload.decode("utf-8", errors="replace").strip()
    if utf8_text.startswith("{"):
        return parse_json_response(utf8_text)

    if requested_format == Format.JSON:
        return parse_json_response(utf8_text)

    decoded = decode_response_bytes(payload, lang=lang)
    return parse_csv_response(decoded)


__all__ = ["decode_response_bytes", "parse_response"]
