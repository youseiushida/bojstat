from bojstat.enums import Format, Lang
from bojstat.types import ParsedResponse

__all__ = ['decode_response_bytes', 'parse_response']

def decode_response_bytes(payload: bytes, *, lang: Lang) -> str:
    """バイト列を言語規約に従ってデコードする。

    Args:
        payload: レスポンスバイト列。
        lang: 指定言語。

    Returns:
        デコード済み文字列。
    """
def parse_response(payload: bytes, *, requested_format: Format, lang: Lang) -> ParsedResponse:
    """レスポンスをJSON/CSV自動判定で解析する。

    Args:
        payload: レスポンスバイト列。
        requested_format: 要求形式。
        lang: 要求言語。

    Returns:
        解析結果。
    """
