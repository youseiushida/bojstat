from bojstat.enums import Format as Format
from bojstat.normalize import normalize_key as normalize_key, parse_date_tolerant as parse_date_tolerant
from bojstat.types import ParsedResponse as ParsedResponse

def parse_json_response(text: str) -> ParsedResponse:
    """JSON本文を解析して共通形式へ変換する。

    Args:
        text: レスポンステキスト。

    Returns:
        解析結果。
    """
