from bojstat.config import ERROR_CATALOG_VERSION as ERROR_CATALOG_VERSION
from bojstat.types import ErrorClassification as ErrorClassification
from dataclasses import dataclass

@dataclass(slots=True)
class ErrorClassifier:
    """MESSAGEID分類器。"""
    catalog_version: str = ...
    def classify(self, *, status: int | None = None, message_id: str) -> ErrorClassification:
        """STATUS/MESSAGEIDから意味カテゴリを返す。

        Args:
            status: STATUS。省略可。
            message_id: MESSAGEID。

        Returns:
            分類結果。
        """
