"""MESSAGEID分類カタログ。"""

from __future__ import annotations

from dataclasses import dataclass

from bojstat.config import ERROR_CATALOG_VERSION
from bojstat.types import ErrorClassification


_CATEGORY_MAP = {
    "M181000I": "ok",
    "M181030I": "no_data",
    "M181001E": "invalid_parameter",
    "M181002E": "invalid_language",
    "M181003E": "invalid_format",
    "M181004E": "missing_db",
    "M181005E": "invalid_db",
    "M181006E": "missing_code",
    "M181007E": "code_count_overflow",
    "M181008E": "invalid_start",
    "M181009E": "invalid_end",
    "M181010E": "period_range",
    "M181011E": "period_order",
    "M181012E": "invalid_start_position",
    "M181013E": "code_not_found",
    "M181014E": "frequency_mismatch",
    "M181015E": "start_format_mismatch",
    "M181016E": "end_format_mismatch",
    "M181017E": "missing_frequency",
    "M181018E": "invalid_frequency",
    "M181019E": "missing_layer",
    "M181020E": "invalid_layer",
    "M181090S": "internal_error",
    "M181091S": "db_unavailable",
}


@dataclass(slots=True)
class ErrorClassifier:
    """MESSAGEID分類器。"""

    catalog_version: str = ERROR_CATALOG_VERSION

    def classify(
        self,
        *,
        status: int | None = None,
        message_id: str,
    ) -> ErrorClassification:
        """STATUS/MESSAGEIDから意味カテゴリを返す。

        Args:
            status: STATUS。省略可。
            message_id: MESSAGEID。

        Returns:
            分類結果。
        """

        normalized = message_id.strip().upper()
        category = _CATEGORY_MAP.get(normalized, "unknown")
        observation_key = f"{status}:{normalized}" if status is not None else normalized
        confidence = 1.0 if category != "unknown" else 0.0
        return ErrorClassification(
            category=category,
            catalog_version=self.catalog_version,
            observation_key=observation_key,
            confidence=confidence,
        )
