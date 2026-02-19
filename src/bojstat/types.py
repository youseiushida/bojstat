"""公開型と内部共通データ構造。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from bojstat.enums import ConflictResolution, Format, OutputOrder


@dataclass(slots=True)
class TimeSeriesRecord:
    """コードAPI/階層APIの正規化済みレコード。

    Attributes:
        series_code: 系列コード。
        series_name: 系列名。
        unit: 単位。
        frequency: 期種表示名。
        frequency_code: 期種コード。
        week_anchor: 週次アンカー。
        category: カテゴリ名。
        last_update: 最終更新日（YYYYMMDD）。
        survey_date: 観測時点。
        value: 観測値。
        original_code_index: 入力コード順序。
        source_page_index: 取得ページ番号。
        source_row_index: ページ内行番号。
        extras: 未知キーの退避領域。
    """

    series_code: str
    series_name: str | None
    unit: str | None
    frequency: str | None
    frequency_code: str | None
    week_anchor: str | None
    category: str | None
    last_update: str | None
    survey_date: str
    value: Decimal | None
    original_code_index: int | None
    source_page_index: int
    source_row_index: int
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MetadataRecord:
    """メタデータAPIの正規化済みレコード。

    Attributes:
        series_code: 系列コード。階層見出し行では空文字。
        series_name: 系列名。
        unit: 単位。
        frequency: 期種表示名。
        category: カテゴリ名。
        layer1: 階層1。
        layer2: 階層2。
        layer3: 階層3。
        layer4: 階層4。
        layer5: 階層5。
        start_of_time_series: 収録開始期。
        end_of_time_series: 収録終了期。
        last_update: 最終更新日。
        notes: 備考。
        extras: 未知キーの退避領域。
    """

    series_code: str
    series_name: str | None
    unit: str | None
    frequency: str | None
    category: str | None
    layer1: str | None
    layer2: str | None
    layer3: str | None
    layer4: str | None
    layer5: str | None
    start_of_time_series: str | None
    end_of_time_series: str | None
    last_update: str | None
    notes: str | None
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ResponseMeta:
    """レスポンス共通メタ情報。

    Attributes:
        status: API本文のSTATUS。
        message_id: API本文のMESSAGEID。
        message: API本文のMESSAGE。
        date_raw: API本文のDATE原文。
        date_parsed: DATEの解析結果。
        date_parse_warning: DATE解析失敗時の警告。
        date_semantics: DATEの意味（api別）。
        next_position: NEXTPOSITION。
        parameters: PARAMETER情報。
        request_url: 実行URL。
        schema_version: スキーマバージョン。
        parser_version: パーサバージョン。
        normalizer_version: 正規化器バージョン。
        resume_token: 再開トークン。
        consistency_signal: 停止/警告シグナル名。
        consistency_details: シグナル詳細。
        conflict_resolution: 競合解決ルール。
        conflicts_count: 競合件数。
        conflicts_sample: 競合サンプル。
        warnings: 警告一覧。
        extras: 追加情報。
    """

    status: int
    message_id: str
    message: str
    date_raw: str | None
    date_parsed: datetime | None
    date_parse_warning: str | None
    date_semantics: str
    next_position: int | None
    parameters: dict[str, str | None]
    request_url: str
    schema_version: str
    parser_version: str
    normalizer_version: str
    resume_token: str | None = None
    consistency_signal: str | None = None
    consistency_details: dict[str, Any] = field(default_factory=dict)
    conflict_resolution: ConflictResolution = ConflictResolution.LATEST_LAST_UPDATE
    conflicts_count: int = 0
    conflicts_sample: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ParsedResponse:
    """パーサ出力。

    Attributes:
        status: API本文STATUS。
        message_id: API本文MESSAGEID。
        message: API本文MESSAGE。
        date_raw: DATE原文。
        date_parsed: DATE解析結果。
        date_parse_warning: DATE解析警告。
        parameters: PARAMETER情報。
        next_position: NEXTPOSITION。
        rows: 正規化前のデータ行。
        db: DB名（メタデータAPI用）。
        raw_response_excerpt: 本文抜粋。
        format: 実レスポンス形式。
    """

    status: int
    message_id: str
    message: str
    date_raw: str | None
    date_parsed: datetime | None
    date_parse_warning: str | None
    parameters: dict[str, str | None]
    next_position: int | None
    rows: list[dict[str, Any]]
    db: str | None
    raw_response_excerpt: str
    format: Format


@dataclass(slots=True)
class ErrorClassification:
    """MESSAGEID分類結果。

    Attributes:
        category: 分類カテゴリ。
        catalog_version: カタログバージョン。
        observation_key: 観測キー。
        confidence: 信頼度。
    """

    category: str
    catalog_version: str
    observation_key: str
    confidence: float


@dataclass(slots=True)
class ResumeTokenState:
    """再開トークンの復元結果。

    Attributes:
        token_version: トークンバージョン。
        api: API名。
        api_origin: API起点情報。
        request_fingerprint: 要求指紋。
        chunk_index: チャンク位置。
        next_position: 次回開始位置。
        lang: 言語。
        format: 出力形式。
        parser_version: パーサバージョン。
        normalizer_version: 正規化器バージョン。
        schema_version: スキーマバージョン。
        code_order_map: 入力コード順序情報。
    """

    token_version: int
    api: Literal["code", "layer"]
    api_origin: str
    request_fingerprint: str
    chunk_index: int
    next_position: int
    lang: str
    format: str
    parser_version: str
    normalizer_version: str
    schema_version: str
    code_order_map: dict[str, int]


@dataclass(slots=True)
class RequestContext:
    """要求実行時の固定コンテキスト。

    Attributes:
        api: API種別。
        endpoint: エンドポイント。
        api_origin: API起点。
        lang: 言語。
        format: 出力形式。
        parser_version: パーサバージョン。
        normalizer_version: 正規化器バージョン。
        schema_version: スキーマバージョン。
        output_order: 出力順序。
    """

    api: Literal["code", "layer", "metadata"]
    endpoint: str
    api_origin: str
    lang: str
    format: str
    parser_version: str
    normalizer_version: str
    schema_version: str
    output_order: OutputOrder
