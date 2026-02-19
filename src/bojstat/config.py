"""設定値定義。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from bojstat.enums import (
    CacheMode,
    ConflictResolution,
    ConsistencyMode,
    Format,
    Lang,
    OutputOrder,
)

PARSER_VERSION = "1.0"
NORMALIZER_VERSION = "1.0"
SCHEMA_VERSION = "1.0"
TOKEN_VERSION = 1
ERROR_CATALOG_VERSION = "2026.02"

DEFAULT_BASE_URL = "https://www.stat-search.boj.or.jp/api/v1"
DEFAULT_USER_AGENT = "bojstat/0.1.0"


@dataclass(slots=True)
class RetryConfig:
    """再試行設定。

    Attributes:
        max_attempts: 最大試行回数。
        transport_max_attempts: 通信例外時の最大試行回数（未指定時はmax_attempts）。
        base_delay: 指数バックオフの基準秒。
        cap_delay: 待機上限秒。
        jitter_ratio: バックオフ待機のゆらぎ係数。
        retry_on_403: 403再試行を有効化するか。
        retry_on_403_max_attempts: 403時の最大試行回数。
    """

    max_attempts: int = 5
    transport_max_attempts: int | None = None
    base_delay: float = 0.5
    cap_delay: float = 8.0
    jitter_ratio: float = 1.0
    retry_on_403: bool = False
    retry_on_403_max_attempts: int = 2


@dataclass(slots=True)
class CacheConfig:
    """キャッシュ設定。

    Attributes:
        mode: キャッシュモード。
        dir: キャッシュディレクトリ。
        ttl_seconds: TTL秒。
        publish_window_start_hour: 更新窓開始時刻（JST時）。
        publish_window_start_minute: 更新窓開始時刻（JST分）。
        publish_window_grace_minutes: 更新窓許容分。
    """

    mode: CacheMode = CacheMode.IF_STALE
    dir: Path | None = None
    ttl_seconds: int = 24 * 60 * 60
    publish_window_start_hour: int = 8
    publish_window_start_minute: int = 50
    publish_window_grace_minutes: int = 90


@dataclass(slots=True)
class ClientConfig:
    """クライアント共通設定。

    Attributes:
        base_url: APIベースURL。
        timeout: タイムアウト秒。
        lang: 言語。
        format: 出力形式。
        user_agent: User-Agent。
        rate_limit_per_sec: 1秒あたり上限回数。
        strict_api: 仕様準拠モード。
        auto_split_codes: 自動分割有効化。
        consistency_mode: 整合性モード。
        conflict_resolution: 競合解決。
        output_order: 出力順序。
        allow_raw_override: raw_params上書き許可。
        metadata_freshness_strict: DATE解析失敗時に例外化するか。
        capture_full_response: 完全文字列の例外保持。
        cache: キャッシュ設定。
    """

    base_url: str = DEFAULT_BASE_URL
    timeout: float = 30.0
    lang: Lang = Lang.JP
    format: Format = Format.JSON
    user_agent: str = DEFAULT_USER_AGENT
    rate_limit_per_sec: float = 1.0
    strict_api: bool = True
    auto_split_codes: bool = False
    consistency_mode: ConsistencyMode = ConsistencyMode.STRICT
    conflict_resolution: ConflictResolution = ConflictResolution.LATEST_LAST_UPDATE
    output_order: OutputOrder = OutputOrder.CANONICAL
    allow_raw_override: bool = False
    metadata_freshness_strict: bool = False
    capture_full_response: bool = False
    cache: CacheConfig = field(default_factory=CacheConfig)
