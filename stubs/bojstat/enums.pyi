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

class DB(StrEnum):
    '''日銀統計DBコードを表す列挙型。

    APIDOC「Ⅱ.3.（2）DB名」記載の全DBコードを列挙する。
    StrEnumのため、文字列としても利用可能（例: DB.CO == "CO"）。
    日本語名エイリアスにも対応（例: DB.短観 is DB.CO）。
    '''
    IR01 = 'IR01'
    基準割引率および基準貸付利率_従来_公定歩合_として掲載されていたもの_の推移 = 'IR01'
    IR02 = 'IR02'
    預金種類別店頭表示金利の平均年利率等 = 'IR02'
    IR03 = 'IR03'
    定期預金の預入期間別平均金利 = 'IR03'
    IR04 = 'IR04'
    貸出約定平均金利 = 'IR04'
    FM01 = 'FM01'
    無担保コール_N物レート_毎営業日 = 'FM01'
    FM02 = 'FM02'
    短期金融市場金利 = 'FM02'
    FM03 = 'FM03'
    短期金融市場残高 = 'FM03'
    FM04 = 'FM04'
    コール市場残高 = 'FM04'
    FM05 = 'FM05'
    公社債発行_償還および現存額 = 'FM05'
    FM06 = 'FM06'
    公社債消化状況_利付国債 = 'FM06'
    FM07 = 'FM07'
    参考_国債窓口販売額_窓口販売率_2004年1月まで = 'FM07'
    FM08 = 'FM08'
    外国為替市況 = 'FM08'
    FM09 = 'FM09'
    実効為替レート = 'FM09'
    PS01 = 'PS01'
    各種決済 = 'PS01'
    PS02 = 'PS02'
    フェイルの発生状況 = 'PS02'
    MD01 = 'MD01'
    マネタリーベース = 'MD01'
    MD02 = 'MD02'
    マネーストック = 'MD02'
    MD03 = 'MD03'
    マネタリーサーベイ = 'MD03'
    MD04 = 'MD04'
    参考_マネーサプライ_M2_CD_増減と信用面の対応 = 'MD04'
    MD05 = 'MD05'
    通貨流通高 = 'MD05'
    MD06 = 'MD06'
    日銀当座預金増減要因と金融調節_実績 = 'MD06'
    MD07 = 'MD07'
    準備預金額 = 'MD07'
    MD08 = 'MD08'
    業態別の日銀当座預金残高 = 'MD08'
    MD09 = 'MD09'
    マネタリーベースと日本銀行の取引 = 'MD09'
    MD10 = 'MD10'
    預金者別預金 = 'MD10'
    MD11 = 'MD11'
    預金_現金_貸出金 = 'MD11'
    MD12 = 'MD12'
    都道府県別預金_現金_貸出金 = 'MD12'
    MD13 = 'MD13'
    貸出_預金動向 = 'MD13'
    MD14 = 'MD14'
    定期預金の残高および新規受入高 = 'MD14'
    LA01 = 'LA01'
    貸出先別貸出金 = 'LA01'
    LA02 = 'LA02'
    日本銀行貸出 = 'LA02'
    LA03 = 'LA03'
    その他貸出残高 = 'LA03'
    LA04 = 'LA04'
    コミットメントライン契約額_利用額 = 'LA04'
    LA05 = 'LA05'
    主要銀行貸出動向アンケート調査 = 'LA05'
    BS01 = 'BS01'
    日本銀行勘定 = 'BS01'
    BS02 = 'BS02'
    民間金融機関の資産_負債 = 'BS02'
    FF = 'FF'
    資金循環 = 'FF'
    OB01 = 'OB01'
    日本銀行の対政府取引 = 'OB01'
    OB02 = 'OB02'
    日本銀行が受入れている担保の残高 = 'OB02'
    CO = 'CO'
    短観 = 'CO'
    PR01 = 'PR01'
    企業物価指数 = 'PR01'
    PR02 = 'PR02'
    企業向けサービス価格指数 = 'PR02'
    PR03 = 'PR03'
    製造業部門別投入_産出物価指数 = 'PR03'
    PR04 = 'PR04'
    サテライト指数_最終需要_中間需要物価指数 = 'PR04'
    PF01 = 'PF01'
    財政資金収支 = 'PF01'
    PF02 = 'PF02'
    政府債務 = 'PF02'
    BIS = 'BIS'
    BIS_国際資金取引統計および国際与信統計の日本分集計結果 = 'BIS'
    BP01 = 'BP01'
    国際収支統計 = 'BP01'
    DER = 'DER'
    デリバティブ取引に関する定例市場報告 = 'DER'
    OT = 'OT'
    その他 = 'OT'

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
