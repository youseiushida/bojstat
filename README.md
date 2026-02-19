# bojstat

日本銀行「時系列統計データ検索サイト」公式 API（2026-02-18 公開）のための、分析実務向け Python クライアントライブラリ。

- 公式API 3種（`getDataCode` / `getDataLayer` / `getMetadata`）をフルカバー
- 通信基盤は `httpx`（初期リリースから同期/非同期 API を提供）
- 型付きパラメータと事前バリデーションで 400 系エラーを最小化
- API別 Pager で `NEXTPOSITION` を追跡（Code/Layer で意味が異なる）
- 階層抽出 1,250 件超過は検知時に、階層分割プランをガイド
- `pandas` / `polars` にワンステップ変換
- リトライ・バックオフ・レート制御・ローカルキャッシュを標準搭載

この README は「完成形」の利用体験がわかるように、推奨 API 設計と使用例を示しています。

## インストール

> 注: ここで示す `pip install` は PyPI 公開後の想定です。

```bash
pip install bojstat
# httpx はコア依存
# 分析用途
pip install "bojstat[dataframe]"
# 既存互換（個別extra指定）も利用可能
pip install "bojstat[pandas,polars]"
# CLI も使う場合
pip install "bojstat[cli]"
```

依存関係の契約（予定）

| Extra | 主な依存 | 用途 |
| --- | --- | --- |
| `dataframe` | `pandas`, `polars` | `to_pandas()`, `to_polars()` |
| `pandas` | `pandas` | `to_pandas()` |
| `polars` | `polars` | `to_polars()` |
| `cli` | `typer`, `rich`, `pyarrow` | CLI 実行、Parquet 出力 |

CLI 出力フォーマットの契約

- `--out *.parquet` は Parquet backend（既定: `pyarrow`）が必要
- backend がない場合は `Parquet backend is required` を明示し、`pip install "bojstat[cli]"` を案内
- `--out *.csv` / `--out *.json` は Parquet backend なしでも利用可能

## HTTP実装方針（httpx）

- デフォルト実装は `httpx.Client` を使用
- 同期 API（`BojClient`）と非同期 API（`AsyncBojClient`）を初期リリースから提供
- `timeout` / `limits` / `proxy` / `http2` は `httpx` 設定をそのまま受け取る
- テスト時は `httpx.MockTransport` で API 応答を差し替え可能
- `with BojClient(...)` / `async with AsyncBojClient(...)` で内部クライアントを自動クローズ
- 外部 `httpx.Client` / `httpx.AsyncClient` を注入する場合は呼び出し側が `close()` / `aclose()` を実行

## 3分クイックスタート

```python
from bojstat import BojClient, Lang, Frequency

with BojClient(
    lang=Lang.JP,
    user_agent="my-team-macro-dashboard/1.0",
    rate_limit_per_sec=1.0,
    cache_dir=".cache/bojstat",
) as client:
    # 1) メタデータ取得（DB: 外国為替市況 FM08）
    meta = client.metadata.get(db="FM08")

    # 2) 系列検索（名称・期種で絞る）
    candidates = meta.find(name_contains="ドル・円", frequency=Frequency.D)
    codes = candidates.head(3).series_codes

    # 3) 時系列取得（欠損は NaN / null として扱える）
    ts = client.data.get_by_code(
        db="FM08",
        code=codes,          # 複数可（同一期種のみ。週次は W0〜W6 混在不可）
        start="202501",      # 公式仕様に合わせた period 指定
        end="202512",
    )

    df = ts.to_pandas()
    pl_df = ts.to_polars()
```

## 目指す使用感

### 1. 公式仕様を隠蔽せず、事故りやすい部分だけ吸収する

- エンドポイントは公式と 1:1 で対応
- ただし以下はライブラリ側で吸収
- `STARTPOSITION` / `NEXTPOSITION` の API 別自動追跡
- Code API: `NEXTPOSITION` は「リクエストで渡した `code` 配列の位置」基準
- Layer API: `NEXTPOSITION` は「DB 内全系列の並び順」基準
- Code/Layer で Pager 実装を分離し、同一アルゴリズムを使い回さない
- Code API は便宜モード（`strict_api=False` かつ `auto_split_codes=True`）でのみ、同一期種の code 群を最大 250 件ずつに分割して処理
- 1チャンク内で `NEXTPOSITION` を追跡し、未完了なら同一チャンクを `STARTPOSITION` 付きで再取得
- `NEXTPOSITION` が未変化/逆行した場合はループ停止して `BojPaginationStalledError` を送出
- 取得途中からの再開用にバージョン付き `resume_token` を公開
- `resume_token` は `token_version` / `api` / `api_origin` / `request_fingerprint` / `chunk_index` / `next_position` / `lang` / `format` / `parser_version` / `normalizer_version` / `schema_version` / `code_order_map` を保持
- `resume_token` 再開時は同一検索条件を必須とし、不一致時は `BojResumeTokenMismatchError` を送出
- 再開取得時は `series_code + survey_date` をキーに重複排除し、欠損/重複なしを保証
- 最終出力は既定 `output_order="canonical"` で `series_code`, `survey_date`, `last_update` の順に安定ソート
- 分割・再開後も code の元順序を保持し、`original_code_index` をメタデータに保持
- 系列 250 / データ数 60,000 の上限は自動ページングで継続取得
- `strict_api=True`（既定）では `code` の順序・構成を変更せずそのまま送信し、`code>1250` は API 仕様どおり `M181007E`（server_response）を返す
- `strict_api=True` では期種混在も自動救済しない（`M181014E` をそのまま返す）
- `strict_api=False` かつ `auto_split_codes=True`（明示 opt-in）でのみ事前分割を有効化
- 階層抽出系列 1,250 超過は自動継続不可のため、検知時に分割条件を提案
- 日付形式ミスの事前検知（`YYYY` / `YYYYHH` / `YYYYQQ` / `YYYYMM`）
- Code API の時期指定は `YYYY` / `YYYYMM` の軽量検証（期種整合は API 応答へ委譲）
- `W` / `D` 指定時の期間指定ルール（開始・終了は `YYYYMM`）と週次混在チェック
- 外部 API へ送るパラメータ値に対してのみ、禁止文字（`< > " ! | ¥ ; '`) と全角文字を拒否
- 年範囲（1850-2050）と開始期 <= 終了期を事前検証
- Layer API は `layer1` 必須、階層は最大 5 要素を検証
- 文字列入力のパラメータは大小文字を区別せず受理し、内部で正規化（例: `db="co"` -> `CO`）

`strict_api` / `auto_split_codes` の組み合わせ契約

| strict_api | auto_split_codes | 挙動 |
| --- | --- | --- |
| `True` | `False` | 既定。仕様準拠。`code>1250` は `M181007E` |
| `True` | `True` | 矛盾設定として初期化時に `ValueError` |
| `False` | `False` | 便宜モード。分割せず API 応答（`M181007E` 含む）を返す |
| `False` | `True` | 便宜モード。事前分割して順次取得 |

Code API ページング状態遷移（擬似コード）

```python
validate_request()
if strict_api and auto_split_codes:
    raise ValueError("strict_api=True と auto_split_codes=True は同時指定不可")

if strict_api:
    chunks = [code_list]  # 仕様準拠: code の順序/構成を保持してそのまま送信
elif auto_split_codes:
    chunks = split_codes_by_frequency_and_size(code_list, chunk_size=250)
else:
    chunks = [code_list]  # strict_api=False かつ auto_split_codes=False

for chunk_index, chunk in enumerate(chunks):
    start_position = load_resume_start(chunk_index, resume_token)  # 初回は 1
    while True:
        resp = get_data_code(db=db, code=chunk, startPosition=start_position)
        emit_records(resp, dedupe_key=("series_code", "survey_date"))

        next_position = resp.next_position
        if not next_position:
            save_resume_token_for_next_chunk(chunk_index + 1, next_position=1)
            break
        if next_position <= start_position:
            raise BojPaginationStalledError(chunk_index=chunk_index, start=start_position, next=next_position)
        start_position = next_position
```

`resume_token` 再開条件

- `api`, `api_origin`, `request_fingerprint`, `chunk_index`, `lang`, `format`, `parser_version`, `normalizer_version`, `schema_version` が一致
- 不一致時は `BojResumeTokenMismatchError`
- 再開時も `series_code + survey_date` で重複排除して欠損/重複なしを保証

`request_fingerprint` 構成要素

- `api_origin`（ホスト + パス + バージョン）, `endpoint`, `db`, `code`（順序込み）, `layer`, `frequency`, `start`, `end`
- `strict_api`, `auto_split_codes`, `consistency_mode`, `conflict_resolution`, `output_order`, `lang`, `format`
- 正規化後 `raw_params`, `parser_version`, `normalizer_version`, `schema_version`

トークン検証失敗の機械可読理由

- `fingerprint_mismatch`
- `chunk_index_mismatch`
- `token_version_mismatch`
- `parser_version_mismatch`
- `normalizer_version_mismatch`

Python 引数と公式パラメータの対応

| Python 引数 | 公式パラメータ |
| --- | --- |
| `db` | `DB` |
| `code` | `CODE` |
| `layer` | `LAYER` |
| `frequency` | `FREQUENCY` |
| `start` | `STARTDATE` |
| `end` | `ENDDATE` |
| `start_position` | `STARTPOSITION` |
| `lang` | `LANG` |
| `format` | `FORMAT` |

`raw_params` の逃げ道

- `raw_params` で未対応パラメータを直接指定可能
- 型付き引数と同名キーが衝突した場合は既定で `ValueError`
- `allow_raw_override=True` でもコア項目（`DB`,`CODE`,`LAYER`,`FREQUENCY`,`STARTDATE`,`ENDDATE`,`STARTPOSITION`,`LANG`,`FORMAT`）の上書きは禁止
- `allow_raw_override=True` は非コア項目の allowlist のみ上書き許可

### 2. 「検索→取得→分析」までをワンストップ

- `metadata` で系列候補探索
- `data` で取得
- CSV/JSON を共通の正規化モデルに変換してから `pandas` / `polars` へ変換
- 欠損値は `null` を壊さず保持しつつ、分析時は NaN として扱える

### 3. 実運用に必要な堅牢性を標準機能化

- エラー判定の主軸は HTTP ステータスではなく本文 `STATUS` / `MESSAGEID`
- HTTP 200 でも本文 `STATUS=400/500/503` なら対応例外を送出
- 本文 `STATUS=400` は非リトライ
- 本文 `STATUS=500/503` は指数バックオフ付き自動リトライ
- `httpx.TimeoutException` / `httpx.ConnectError` / `httpx.ReadError` / `httpx.RemoteProtocolError`: 自動リトライ対象
- `httpx.InvalidURL` / `httpx.LocalProtocolError` / 証明書エラーなど恒久失敗は非リトライ
- HTTP ステータスは本文が欠落/破損して判定不能な場合のフォールバックとして利用
- `200 + M181030I`（該当データなし）は例外にせず空データで返却
- 高頻度アクセス抑制（レート制御）
- ローカルキャッシュ（ETag / Last-Modified が使える場合は HTTP キャッシュ優先）
- APIレスポンスの `STATUS` / `MESSAGEID` / `DATE` を常に参照可能
- `consistency_mode="strict"` は停止シグナルを機械可読に判定
- 停止シグナル `window_crossed`: 取得中に JST 08:50 頃の更新ウィンドウを跨いだ
- 停止シグナル `last_update_conflict`: 同一 `series_code + survey_date` の `last_update` が不整合
- `consistency_mode="best_effort"` では上記シグナルを警告として記録し、取得を継続
- `best_effort` の重複/衝突解決は `conflict_resolution="latest_last_update"` を既定とする
- 同値時は `source_page_index`, `source_row_index` の順で決定し、結果を決定論的に固定
- `meta.conflict_resolution` に採用ルールを保存
- 破棄した競合行は `meta.conflicts_count` と `meta.conflicts_sample`（件数上限つき）で監査可能に保持
- `meta.consistency_signal` と `meta.consistency_details` に停止/警告理由を保存
- 既定レート制御は `rate_limit_per_sec=1.0`（最小間隔 1 秒）
- バックオフは full jitter（`sleep = random(0, min(cap, base * 2**attempt))`）
- `retry_transport_max_attempts` で通信例外時の再試行上限を個別調整可能（本文STATUS再試行上限は `retry_max_attempts`）
- `retry_jitter_ratio` でバックオフ待機のゆらぎ幅を調整可能
- `Retry-After` ヘッダがある場合はそれを優先し、ローカル最小間隔と比較して長い方を採用
- HTTP `429` は throttling として再試行候補
- HTTP `403` は既定で非再試行。`Retry-After` があり `retry_on_403=True` の場合のみ短回数（既定2回）再試行
- 待機時間は `max(retry_after, local_min_interval_remaining, full_jitter_backoff)` で統合決定

### 4. 文字コードと日時メタ情報を明示する

- JSON は UTF-8
- CSV は `lang=jp` のとき Shift-JIS、`lang=en` のとき UTF-8 でデコード
- CSV はメタ行（`STATUS`/`PARAMETER`/`NEXTPOSITION`）とデータ行が混在するため、専用パーサで吸収
- CSV のブランク値（例: `NEXTPOSITION` 未設定）は `None` として正規化
- `DATE` は API 種別で意味が異なる
- Code/Layer API: 出力ファイル作成日時
- Metadata API: システム内部データ作成日時（ファイル作成日時ではない）
- `date_raw` は受信文字列を常に保持
- `date_parsed` は tolerant parser で別フィールド化（フォーマット揺れを許容）
- `date_parsed` に失敗しても例外化せず、`date_parse_warning` を記録して処理継続
- Metadata 鮮度判定で `date_parsed` 失敗時は `freshness_mode="ttl_only"` にフォールバック
- `metadata_freshness_strict=True` の場合は `BojDateParseError` を送出

### 5. 仕様変更に強い正規化

- マニュアル記載のサンプルは開発段階で変更される前提で扱う
- レスポンスキーの揺れ（例: スペース/アンダースコア差）に頑健な正規化レイヤを持つ
- 内部の公開モデルは固定フィールド名にマップし、未知キーは `extras` に退避

### 6. キャッシュ再現性ポリシー

- キャッシュモードを `if_stale` / `force_refresh` / `off` で明示的に選択可能
- 既定 TTL は 24 時間（`cache_ttl` で変更可能）
- 更新ウィンドウは設定可能（既定: `publish_window_start=08:50 JST`, `publish_window_grace=90m`）
- stale 判定は固定時刻ではなく、観測した `DATE` / `LAST_UPDATE` と更新ウィンドウを組み合わせた動的判定
- Metadata は `DATE`（内部データ作成時刻）を鮮度検証に利用
- Code/Layer は `DATE`（出力作成時刻）を鮮度根拠に使わず、TTL と `LAST_UPDATE` スナップショットで検証
- キャッシュキーは canonical request + `api_origin` + `lang` + `format` + `parser_version` + `normalizer_version` + `schema_version` + `strict_api` + `auto_split_codes` + `consistency_mode` + `conflict_resolution` + `output_order` で構成
- キャッシュエントリに `complete=true|false` を保持し、`complete=true` のみ通常ヒット対象
- ページング途中失敗時は `complete=false` で保存し、再開時にのみ参照（通常読み出しでは不採用）
- キャッシュ書き込みは lock + atomic rename で実施し、並行実行時の破損を防止
- 破損検知時は当該エントリを隔離して再取得し、全体処理は継続

### 7. テスト戦略（ゴールデンテスト）

- CSV デコード: `lang=jp` は Shift-JIS、`lang=en` は UTF-8
- `NEXTPOSITION` の `null`（JSON）/ブランク（CSV）差分を同一意味に正規化
- `DATE` 意味差（Code/Layer は出力時刻、Metadata は内部データ時刻）を検証
- キー揺れ（スペース/アンダースコア差）を含むレスポンスで正規化後モデルが一致することを検証
- CodePager で「進捗しない `NEXTPOSITION`」を検知して停止することを検証
- HTTP 200 + 本文 `STATUS=400` を正しくエラー化することを検証
- Code/Layer の再開取得で「欠損なし・重複なし」を検証
- resume あり/なしで出力順序が `output_order="canonical"` で一致することを検証
- 大文字小文字が混在した入力（例: `db=co`, `lang=Jp`）を正規化できることを検証
- `strict_api=True/False` で `code>1250` の挙動が契約どおり切り替わることを検証
- `strict_api=True` で期種混在コードを自動救済せず `M181014E` を返すことを検証
- `consistency_mode=strict/best_effort` で更新ウィンドウ跨ぎ・`LAST_UPDATE` 不整合の挙動を検証
- Code/Layer で別 fixture を用意し、`STARTPOSITION` 再開契約（意味差・欠損なし・重複なし）をプロパティテスト化
- Code API 60,000件境界の固定fixtureを追加
- 1コード長期間（1系列で 60,000 超え）
- 複数コード混在（系列数×期数で 60,000 超え）
- `NEXTPOSITION` 複数周回（2回以上の継続取得）
- 部分取得キャッシュ（`complete=false`）が通常ヒットに使われないことを検証
- 仮想時計で backoff（full jitter）の決定論テストを実施（seed 固定）
- `Retry-After` 優先ルールの統合待機時間を検証
- `retry_on_403` の有効/無効で再試行分岐が切り替わることを検証
- 並行リクエスト時もグローバルレート上限を超えないことを検証
- `format=csv` 指定でもエラー時は JSON 応答になることを検証
- 言語判定前エラーでメッセージ言語が英語フォールバックになることを検証
- Python引数→公式パラメータの 1:1 マッピングと `raw_params` 衝突時の挙動を検証
- `DATE` の `date_raw/date_parsed` 契約（揺れ許容・警告記録）を検証

## API イメージ

```python
from bojstat import BojClient, Frequency, BojApiError

with BojClient(timeout=30.0) as client:
    try:
        # Code API（getDataCode）
        r1 = client.data.get_by_code(
            db="co",  # 大小文字は内部で正規化
            code=["TK99F1000601GCQ01000", "TK99F2000601GCQ01000"],
            start="202401",
            end="202504",
            strict_api=True,
        )

        # Layer API（getDataLayer）
        r2 = client.data.get_by_layer(
            db="MD10",
            frequency=Frequency.Q,
            layer="1,*",
            start=None,
            end=None,
            auto_paginate=True,  # LayerPager を使用。1,250超過は別途 layer 分割が必要
            consistency_mode="strict",
        )

        # Metadata API（getMetadata）
        m = client.metadata.get(db="PR01")

    except BojApiError as e:
        print(e.status)      # 400 / 500 / 503
        print(e.message_id)  # M1810xx...
        print(e.message)
```

```python
# 非同期 API イメージ
from bojstat import AsyncBojClient, Frequency

async def run() -> None:
    async with AsyncBojClient(timeout=30.0) as client:
        result = await client.data.get_by_layer(
            db="MD10",
            frequency=Frequency.Q,
            layer="1,*",
            auto_paginate=True,
        )
        print(result.meta.message_id)
```

```python
# エラー分類 API イメージ（推奨: STATUS と MESSAGEID を渡す）
info = client.errors.classify(status=400, message_id="M181014E")
print(info.category)         # "frequency_mismatch"
print(info.catalog_version)  # 例: "2026.02"

# message_id 単独版は補助的に提供（confidence 付き）
unknown = client.errors.classify(message_id="M181999E")
print(unknown.category)         # "unknown"
print(unknown.observation_key)  # 例: "400:M181999E"
print(unknown.confidence)       # 0.0–1.0
```

## データモデル（分析しやすい返り値）

`TimeSeriesFrame`（共通返却オブジェクト）

- `records`: 正規化済み行データ
- `meta`: 要求パラメータ、`NEXTPOSITION`、`resume_token`、`schema_version`、`status`、`message_id`、`message`、`date_raw`、`date_parsed`、`date_semantics`
- `to_pandas()`
- `to_polars()`
- `to_long()` / `to_wide()`

基本カラム（Code/Layer API）

- `series_code`
- `series_name`
- `unit`
- `frequency`
- `frequency_code`（`W0`..`W6`, `Q`, `M` などの正規化コード）
- `week_anchor`（週次のみ `MONDAY`..`SUNDAY`、それ以外は `None`）
- `category`
- `last_update` (`YYYYMMDD`)
- `survey_date`（出力は期種に応じて `YYYY`/`YYYYHH`/`YYYYQQ`/`YYYYMM`/`YYYYMMDD`）
- `value`（欠損は `None`。数値は既定で `Decimal` 保持）
- `original_code_index`（auto_split 時も元のコード順を保持。strict_api では入力順と一致）

数値精度ポリシー

- 内部保持は `Decimal`（精度保持優先）
- `to_pandas()` / `to_polars()` では `numeric_mode="decimal|float64|string"` を選択可能
- 変換時既定は `float64`（分析ワークフロー優先）
- 厳密精度が必要な場合は `numeric_mode="decimal"` を明示指定

`MetadataFrame`（メタデータ専用返却オブジェクト）

- `series_code`（階層ノード行では空文字を許容）
- `series_name`
- `unit`
- `frequency`
- `category`
- `layer1` .. `layer5`
- `start_of_time_series`
- `end_of_time_series`
- `last_update`
- `notes`

メタデータ正規化規約

- `SERIES_CODE` が空の行は階層見出しノードとして保持（除外しない）
- `NOTES_J` / `NOTES` は `notes` に正規化し、元フィールドは `extras` に保持可能
- 収録期間列（開始/終了）は period 型へ正規化し、原文も保持可能

スキーマ互換ポリシー

- `TimeSeriesFrame.meta.schema_version` と `MetadataFrame.meta.schema_version` を常に付与
- 後方互換な変更（列追加・nullable 拡張）はマイナー更新で提供
- 非互換な変更（列削除・型変更）はメジャー更新でのみ実施

## CLI（完成形イメージ）

```bash
# メタデータ取得
bojstat metadata --db FM08 --lang jp --out fm08_meta.parquet

# 系列コード指定で時系列取得
bojstat code \
  --db CO \
  --code TK99F1000601GCQ01000,TK99F2000601GCQ01000 \
  --start 202401 --end 202504 \
  --out tankan.parquet

# 階層指定で取得（自動ページング）
bojstat layer \
  --db MD10 --frequency Q --layer "1,*" \
  --out md10_q.parquet
```

## エラー/空結果設計（公式 MESSAGEID 準拠）

- `BojBadRequestError`（本文 `STATUS=400`）
- `BojServerError`（本文 `STATUS=500`）
- `BojUnavailableError`（本文 `STATUS=503`）
- `BojGatewayError`（上流ゲートウェイ等で本文解析不能。`message_id=UNPARSEABLE_RESPONSE`）
- `M181030I` は正常終了として扱い、空の `TimeSeriesFrame` を返す（デフォルト）
- `MESSAGEID` を意味カテゴリへ分類する API を公開（復旧/再試行判断に使用）
- 未知 `MESSAGEID` は必ず `unknown` に分類し、`message_id` 原文は透過して保持
- 分類カタログは `catalog_version` を持ち、結果に `observation_key` を付与
- HTTP ステータスのみで判定せず、本文 `STATUS` / `MESSAGEID` を優先
- 例外は `origin` を持つ（`server_response` / `client_validation` / `transport`）
- `server_response` は API 応答由来（`status`, `message_id`, `date_raw`, `raw_response_excerpt` を保持）
- `client_validation` は送信前検証由来（`validation_code` を保持）

例外には `status`, `message_id`, `message`, `request_url`, `raw_response_excerpt`（サイズ上限付き）を保持します。
完全な本文は `capture_full_response=True` の場合のみ `raw_response` を保持します。

## 公式仕様準拠の注意点

- `code` は「系列コード」を指定（`DB名+系列コード` 形式は不可）
- `code` で複数指定する場合は同一期種のみ
- 週次は内部的に `W0`〜`W6` が存在し、Code API では混在不可（必要なら分割リクエスト）
- Layer API で `frequency=W` を指定した場合、条件一致した週次系列は全て対象
- パラメータ名/値は大小文字を区別しないため、文字列入力は case-insensitive で受理して正規化
- Code API の `code` 指定数は 1,250 超過でエラー（`M181007E`）
- 一部の上流経路では `M181007E` ではなく HTML 400 になる場合があり、この場合は `BojGatewayError` として扱う
- 便利モードで `code` 自動分割を使う場合も既定は `strict_api=True`。明示 opt-in 時のみ分割実行
- `layer` は最大5階層（`*` ワイルドカード可）
- 1回の取得上限（Code API / Layer API）
- 検索可能な系列数: 250
- 検索可能なデータ数: 60,000（系列数×期数）
- 階層で抽出される系列数: 1,250（期種絞り込み前の件数で判定。超過時はエラーで出力なし）
- エラー時の応答は常に JSON（`format=csv` 指定でも JSON）

## 標準ライブラリを狙うための公開方針

- セマンティックバージョニング（`MAJOR.MINOR.PATCH`）
- 変更履歴（Breaking Change を明記）
- 日次スモークテスト（固定系列を取得してスキーマ変化検知）
- 日本語 / 英語ドキュメント
- 利用時の留意点（過剰アクセス防止、問い合わせ先）を明示

## ライセンス

MIT
