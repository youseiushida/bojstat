"""例外定義。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class BojErrorContext:
    """例外に付随する共通コンテキスト。

    Attributes:
        request_url: リクエストURL。
        raw_response_excerpt: レスポンス抜粋。
        raw_response: 完全レスポンス。
    """

    request_url: str | None = None
    raw_response_excerpt: str | None = None
    raw_response: str | None = None


class BojError(Exception):
    """ライブラリ例外の基底クラス。

    Attributes:
        origin: 例外発生元。
        context: 追加コンテキスト。
    """

    def __init__(
        self,
        message: str,
        *,
        origin: str,
        context: BojErrorContext | None = None,
    ) -> None:
        super().__init__(message)
        self.origin = origin
        self.context = context or BojErrorContext()


class BojApiError(BojError):
    """API本文由来の例外。"""

    def __init__(
        self,
        message: str,
        *,
        status: int,
        message_id: str,
        request_url: str,
        raw_response_excerpt: str | None = None,
        raw_response: str | None = None,
    ) -> None:
        super().__init__(
            message,
            origin="server_response",
            context=BojErrorContext(
                request_url=request_url,
                raw_response_excerpt=raw_response_excerpt,
                raw_response=raw_response,
            ),
        )
        self.status = status
        self.message_id = message_id
        self.message = message


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

    def __init__(self, message: str, *, request_url: str | None = None) -> None:
        super().__init__(
            message,
            origin="transport",
            context=BojErrorContext(request_url=request_url),
        )


class BojValidationError(BojError):
    """送信前バリデーションエラー。"""

    def __init__(self, message: str, *, validation_code: str) -> None:
        super().__init__(message, origin="client_validation")
        self.validation_code = validation_code


class BojResumeTokenMismatchError(BojError):
    """再開トークン検証不一致。"""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message, origin="client_validation")
        self.reason = reason


class BojPaginationStalledError(BojError):
    """ページング進捗停止。"""

    def __init__(self, *, chunk_index: int, start: int, next_position: int) -> None:
        super().__init__(
            (
                "NEXTPOSITION が進行しないため停止しました: "
                f"chunk_index={chunk_index}, start={start}, next={next_position}"
            ),
            origin="server_response",
        )
        self.chunk_index = chunk_index
        self.start = start
        self.next_position = next_position


class BojDateParseError(BojError):
    """DATE解析失敗。"""

    def __init__(self, message: str) -> None:
        super().__init__(message, origin="client_validation")



class BojConsistencyError(BojError):
    """整合性モード strict での停止例外。"""

    def __init__(self, *, signal: str, details: dict[str, object]) -> None:
        super().__init__(f"整合性エラー: {signal}", origin="server_response")
        self.signal = signal
        self.details = details
