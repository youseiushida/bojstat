from enum import StrEnum

class Lang(StrEnum):
    """API言語を表す列挙型。

    Attributes:
        JP: 日本語。
        EN: 英語。
    """
    JP = 'JP'
    EN = 'EN'

class Format(StrEnum):
    """API出力形式を表す列挙型。

    Attributes:
        JSON: JSON形式。
        CSV: CSV形式。
    """
    JSON = 'JSON'
    CSV = 'CSV'

class Frequency(StrEnum):
    """期種を表す列挙型。

    Attributes:
        CY: 暦年。
        FY: 年度。
        CH: 暦年半期。
        FH: 年度半期。
        Q: 四半期。
        M: 月次。
        W: 週次。
        D: 日次。
    """
    CY = 'CY'
    FY = 'FY'
    CH = 'CH'
    FH = 'FH'
    Q = 'Q'
    M = 'M'
    W = 'W'
    D = 'D'

class CacheMode(StrEnum):
    """キャッシュ利用モード。

    Attributes:
        IF_STALE: stale時のみ更新。
        FORCE_REFRESH: 常に再取得。
        OFF: キャッシュ無効。
    """
    IF_STALE = 'if_stale'
    FORCE_REFRESH = 'force_refresh'
    OFF = 'off'

class ConsistencyMode(StrEnum):
    """整合性検証モード。

    Attributes:
        STRICT: 検知時に停止。
        BEST_EFFORT: 警告化して継続。
    """
    STRICT = 'strict'
    BEST_EFFORT = 'best_effort'

class ConflictResolution(StrEnum):
    """競合解決ルール。

    Attributes:
        LATEST_LAST_UPDATE: LAST_UPDATEが新しい行を採用。
    """
    LATEST_LAST_UPDATE = 'latest_last_update'

class OutputOrder(StrEnum):
    """出力並び順。

    Attributes:
        CANONICAL: 仕様で定義した安定順序。
    """
    CANONICAL = 'canonical'
