from _typeshed import Incomplete
from dataclasses import dataclass

@dataclass(slots=True)
class BojErrorContext:
    """例外に付随する共通コンテキスト。

    Attributes:
        request_url: リクエストURL。
        raw_response_excerpt: レスポンス抜粋。
        raw_response: 完全レスポンス。
    """
    request_url: str | None = ...
    raw_response_excerpt: str | None = ...
    raw_response: str | None = ...

class BojError(Exception):
    """ライブラリ例外の基底クラス。

    Attributes:
        origin: 例外発生元。
        context: 追加コンテキスト。
    """
    origin: Incomplete
    context: Incomplete
    def __init__(self, message: str, *, origin: str, context: BojErrorContext | None = None) -> None: ...

class BojApiError(BojError):
    """API本文由来の例外。"""
    status: Incomplete
    message_id: Incomplete
    message: Incomplete
    def __init__(self, message: str, *, status: int, message_id: str, request_url: str, raw_response_excerpt: str | None = None, raw_response: str | None = None) -> None: ...

class BojBadRequestError(BojApiError):
    """STATUS=400の例外。"""
class BojServerError(BojApiError):
    """STATUS=500の例外。"""
class BojUnavailableError(BojApiError):
    """STATUS=503の例外。"""
class BojGatewayError(BojApiError):
    """上流ゲートウェイ等の非JSONエラー応答。"""

class BojTransportError(BojError):
    """HTTP通信層の例外。"""
    def __init__(self, message: str, *, request_url: str | None = None) -> None: ...

class BojValidationError(BojError):
    """送信前バリデーションエラー。"""
    validation_code: Incomplete
    def __init__(self, message: str, *, validation_code: str) -> None: ...

class BojResumeTokenMismatchError(BojError):
    """再開トークン検証不一致。"""
    reason: Incomplete
    def __init__(self, message: str, *, reason: str) -> None: ...

class BojPaginationStalledError(BojError):
    """ページング進捗停止。"""
    chunk_index: Incomplete
    start: Incomplete
    next_position: Incomplete
    def __init__(self, *, chunk_index: int, start: int, next_position: int) -> None: ...

class BojDateParseError(BojError):
    """DATE解析失敗。"""
    def __init__(self, message: str) -> None: ...

class BojConsistencyError(BojError):
    """整合性モード strict での停止例外。"""
    signal: Incomplete
    details: Incomplete
    def __init__(self, *, signal: str, details: dict[str, object]) -> None: ...
