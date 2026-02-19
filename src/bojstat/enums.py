"""列挙型定義。"""

from __future__ import annotations

from enum import StrEnum


class Lang(StrEnum):
    """API言語を表す列挙型。

    Attributes:
        JP: 日本語。
        EN: 英語。
    """

    JP = "JP"
    EN = "EN"


class Format(StrEnum):
    """API出力形式を表す列挙型。

    Attributes:
        JSON: JSON形式。
        CSV: CSV形式。
    """

    JSON = "JSON"
    CSV = "CSV"


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

    CY = "CY"
    FY = "FY"
    CH = "CH"
    FH = "FH"
    Q = "Q"
    M = "M"
    W = "W"
    D = "D"


class DB(StrEnum):
    """日銀統計DBコードを表す列挙型。

    APIDOC「Ⅱ.3.（2）DB名」記載の全DBコードを列挙する。
    StrEnumのため、文字列としても利用可能（例: DB.CO == "CO"）。
    """

    # 金利（預金・貸出関連）
    IR01 = "IR01"
    IR02 = "IR02"
    IR03 = "IR03"
    IR04 = "IR04"
    # マーケット関連
    FM01 = "FM01"
    FM02 = "FM02"
    FM03 = "FM03"
    FM04 = "FM04"
    FM05 = "FM05"
    FM06 = "FM06"
    FM07 = "FM07"
    FM08 = "FM08"
    FM09 = "FM09"
    # 決済関連
    PS01 = "PS01"
    PS02 = "PS02"
    # 預金・マネー・貸出
    MD01 = "MD01"
    MD02 = "MD02"
    MD03 = "MD03"
    MD04 = "MD04"
    MD05 = "MD05"
    MD06 = "MD06"
    MD07 = "MD07"
    MD08 = "MD08"
    MD09 = "MD09"
    MD10 = "MD10"
    MD11 = "MD11"
    MD12 = "MD12"
    MD13 = "MD13"
    MD14 = "MD14"
    LA01 = "LA01"
    LA02 = "LA02"
    LA03 = "LA03"
    LA04 = "LA04"
    LA05 = "LA05"
    # 金融機関バランスシート
    BS01 = "BS01"
    BS02 = "BS02"
    # 資金循環
    FF = "FF"
    # その他の日本銀行関連
    OB01 = "OB01"
    OB02 = "OB02"
    # 短観
    CO = "CO"
    # 物価
    PR01 = "PR01"
    PR02 = "PR02"
    PR03 = "PR03"
    PR04 = "PR04"
    # 財政関連
    PF01 = "PF01"
    PF02 = "PF02"
    # 国際収支・BIS関連
    BIS = "BIS"
    BP01 = "BP01"
    DER = "DER"
    # その他
    OT = "OT"


class CacheMode(StrEnum):
    """キャッシュ利用モード。

    Attributes:
        IF_STALE: stale時のみ更新。
        FORCE_REFRESH: 常に再取得。
        OFF: キャッシュ無効。
    """

    IF_STALE = "if_stale"
    FORCE_REFRESH = "force_refresh"
    OFF = "off"


class ConsistencyMode(StrEnum):
    """整合性検証モード。

    Attributes:
        STRICT: 検知時に停止。
        BEST_EFFORT: 警告化して継続。
    """

    STRICT = "strict"
    BEST_EFFORT = "best_effort"


class ConflictResolution(StrEnum):
    """競合解決ルール。

    Attributes:
        LATEST_LAST_UPDATE: LAST_UPDATEが新しい行を採用。
    """

    LATEST_LAST_UPDATE = "latest_last_update"


class OutputOrder(StrEnum):
    """出力並び順。

    Attributes:
        CANONICAL: 仕様で定義した安定順序。
    """

    CANONICAL = "canonical"
