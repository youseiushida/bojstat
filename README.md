# bojstat — 日本銀行 時系列統計データ Python クライアント

[![PyPI version](https://img.shields.io/pypi/v/bojstat-py.svg)](https://pypi.org/project/bojstat-py/)
[![Python](https://img.shields.io/pypi/pyversions/bojstat-py.svg)](https://pypi.org/project/bojstat-py/)
[![Context7 Indexed](https://img.shields.io/badge/Context7-Indexed-047857)](https://context7.com/youseiushida/bojstat)
[![Context7 llms.txt](https://img.shields.io/badge/Context7-llms.txt-047857)](https://context7.com/youseiushida/bojstat/llms.txt)

**bojstat** は、[日本銀行 時系列統計データ検索サイト](https://www.stat-search.boj.or.jp/)の API に対応した Python クライアントライブラリです。コード API・階層 API・メタデータ API の 3 種すべてをサポートし、同期・非同期クライアント、自動ページング、ローカルキャッシュ、リトライ、pandas / polars 変換を提供します。内部の HTTP 通信には [httpx](https://github.com/encode/httpx) を使用しています。

[GitHub Repository](https://github.com/youseiushida/bojstat)

[すぐに試せるColab😼](https://colab.research.google.com/drive/1dY9DdZ0pykO6ZCFZhHoxHE-P5T66X4PB?usp=sharing)

## インストール

```sh
pip install bojstat-py
```

オプション依存:

```sh
# pandas 連携
pip install 'bojstat-py[pandas]'

# polars 連携
pip install 'bojstat-py[polars]'

# pandas + polars 両方
pip install 'bojstat-py[dataframe]'

# CLI（typer + rich + pyarrow）
pip install 'bojstat-py[cli]'
```

## クイックスタート

API キーは不要です。インストールしたらすぐに使えます。

```python
from bojstat import BojClient, DB

with BojClient() as client:
    # 短観（CO）の業況判断 DI を取得
    frame = client.data.get_by_code(
        db=DB.短観,
        code="TK99F1000601GCQ01000",
        start="202401",
        end="202504",
    )

# with BojClient() as client:
#     # 短観（CO）の業況判断 DI を取得
#     frame = client.data.get_by_code(
#         db=DB.CO,
#         code="TK99F1000601GCQ01000",
#         start="202401",
#         end="202504",
#     )

for record in frame.records:
    print(record.survey_date, record.value)
```

## DB の発見

50 種の DB コードはすべて `DB` enum と静的カタログに組み込まれています。API ドキュメントを参照する必要はありません。

```python
from bojstat import list_dbs, get_db_info, DB

# 全 DB 一覧
for info in list_dbs():
    print(info)  # "IR01: 基準割引率および基準貸付利率（従来…）の推移"

# カテゴリで絞り込み
for info in list_dbs(category="マーケット"):
    print(info.code, info.name_ja, info.category_ja)

# 個別の DB 情報
info = get_db_info("FM08")
print(info.name_ja)      # "外国為替市況"
print(info.category_ja)  # "マーケット関連"

# DB enum は StrEnum なので文字列としても動作
print(DB.FM08 == "FM08")  # True
```

## 日本語エイリアス

`DB` enum には日本語名のエイリアスが定義されています。IDE の補完機能で日本語名から DB を指定できます。

```python
from bojstat import DB

# 日本語名で指定（エイリアスなので同一オブジェクト）
DB.短観 is DB.CO          # True
DB.外国為替市況 is DB.FM08  # True

# 文字列としても動作
DB.短観 == "CO"            # True
```

## 系列コードの発見

メタデータ API と `find()` メソッドを組み合わせることで、系列コードをプログラム的に発見できます。

```python
from bojstat import BojClient, DB

with BojClient() as client:
    meta = client.metadata.get(db=DB.外国為替市況)

    # 系列名で絞り込み
    hits = meta.find(name_contains="ドル")
    print(hits.series_codes[:5])  # ['FXERD01', 'FXERD02', ...]

    # 期種で絞り込み
    daily = meta.find(frequency="DAILY")
    print(len(daily.records))

    # 組み合わせ検索
    result = meta.find(name_contains="ドル", frequency="DAILY")
    for rec in result.records[:5]:
        print(rec.series_code, rec.series_name)

    # filter() で任意の条件を指定
    hits = meta.filter(lambda r: r.category == "外国為替市況" and r.layer1 == "1")
    print(hits.series_codes)

    # find() と filter() のチェーン
    result = meta.find(name_contains="ドル").filter(lambda r: r.unit == "円")
```

## 使い方

### コード API

系列コードを指定して時系列データを取得します。

```python
from bojstat import BojClient, DB

with BojClient() as client:
    frame = client.data.get_by_code(
        db=DB.外国為替市況,
        code="FXERD01",         # 単一コード（文字列）
        start="202401",
        end="202412",
    )
    print(frame.meta.status)    # 200
    print(len(frame.records))   # レコード数

    for rec in frame.records:
        print(rec.survey_date, rec.value, rec.unit)
```

複数の系列コードを同時に取得:

```python
frame = client.data.get_by_code(
    db=DB.外国為替市況,
    code=["FXERD01", "FXERD02"],  # リストで複数指定
    start="202401",
)
```

### 階層 API

階層情報を指定して時系列データを取得します。

```python
from bojstat import BojClient, DB

with BojClient() as client:
    frame = client.data.get_by_layer(
        db=DB.国際収支統計,
        frequency="M",              # 月次
        layer=[1, 1, 1],            # 階層1=1, 階層2=1, 階層3=1
        start="202504",
        end="202509",
    )
    for rec in frame.records:
        print(rec.series_code, rec.survey_date, rec.value)
```

ワイルドカード指定（大規模DBでも自動でCode API経由に切り替え）:

```python
frame = client.data.get_by_layer(
    db=DB.資金循環,
    frequency="Q",
    layer="*",  # 全階層
    start="202401",
    end="202404",
)
```

> `layer="*"` で系列数が1,250を超える場合、メタデータ経由で系列コードを特定し Code API に自動委譲します（デフォルト有効）。`resolve_wildcard=False` で無効化可能。部分ワイルドカード（`layer=["1", "*"]`）は現時点では自動解決の対象外です。

### メタデータ API

DB 内の全系列のメタ情報（系列コード、名称、期種、階層、収録期間など）を取得します。

```python
from bojstat import BojClient, DB

with BojClient() as client:
    meta = client.metadata.get(db=DB.IR01)

    # 全系列コード一覧
    print(meta.series_codes)

    # 先頭 5 件
    for rec in meta.head(5).records:
        print(rec.series_code, rec.series_name, rec.frequency)
```

## 非同期クライアント

`AsyncBojClient` をインポートし、`await` を付けるだけです。API は同期版と同一です。

```python
import asyncio
from bojstat import AsyncBojClient, DB

async def main():
    async with AsyncBojClient() as client:
        frame = await client.data.get_by_code(
            db=DB.短観,
            code="TK99F1000601GCQ01000",
            start="202401",
        )
        print(len(frame.records))

asyncio.run(main())
```

## pandas / polars 変換

### pandas

```python
from bojstat import BojClient, DB

with BojClient() as client:
    frame = client.data.get_by_code(
        db=DB.外国為替市況,
        code="FXERD01",
        start="202401",
    )
    df = frame.to_pandas()
    print(df[["survey_date", "value"]].head())
```

### polars

```python
df = frame.to_polars()
print(df.select(["survey_date", "value"]).head())
```

### メタデータの DataFrame 変換

```python
meta = client.metadata.get(db=DB.外国為替市況)
df = meta.to_pandas()  # or meta.to_polars()
print(df.columns.tolist())
```

### 出力形式

時系列データは `to_long()` で辞書リスト（long 形式）、`to_wide()` で pivot 形式に変換できます。

```python
# long 形式（デフォルト: float64）
rows = frame.to_long()

# Decimal 精度を維持
rows = frame.to_long(numeric_mode="decimal")

# wide 形式（series_code が列名）
pivot = frame.to_wide()
```

## 自動ページング

日銀 API には 1 リクエストあたり 250 系列 / 60,000 件の上限があります。bojstat はこれを自動的にハンドリングし、`NEXTPOSITION` を追跡して全データを透過的に取得します。

```python
# 階層 API: auto_paginate=True（デフォルト）で全ページ自動取得
frame = client.data.get_by_layer(
    db=DB.国際収支統計,
    frequency="M",
    layer=[1, 1, 1],
    start="202401",
)
# frame.records に全レコードが格納される
```

手動ページングが必要な場合:

```python
frame = client.data.get_by_layer(
    db=DB.国際収支統計,
    frequency="M",
    layer=[1, 1, 1],
    start="202401",
    auto_paginate=False,  # 1 ページだけ取得
)
print(frame.meta.next_position)  # 次回開始位置（None なら全取得済み）
```

## キャッシュ

デフォルトでは、`cache_dir` を指定するとローカルファイルキャッシュが有効になります。TTL（デフォルト 24 時間）内は API を呼ばずにキャッシュから返却します。

```python
from bojstat import BojClient, CacheMode

client = BojClient(
    cache_dir="./cache",          # キャッシュディレクトリ
    cache_ttl=60 * 60 * 12,       # 12 時間
)

# キャッシュモードの変更
client = BojClient(
    cache_dir="./cache",
    cache_mode=CacheMode.FORCE_REFRESH,  # 常に再取得
)

# キャッシュ無効化
client = BojClient(
    cache_mode=CacheMode.OFF,
)
```

## エラーハンドリング

API エラーや通信エラーは、種別に応じた例外クラスで送出されます。すべての例外は `BojError` を継承しています。

```python
import bojstat
from bojstat import BojClient

with BojClient() as client:
    try:
        frame = client.data.get_by_code(db="INVALID", code="XXX")
    except bojstat.BojBadRequestError as e:
        # STATUS=400（パラメータ誤り）
        print(e.status, e.message_id, e.message)
    except bojstat.BojServerError as e:
        # STATUS=500（サーバーエラー）
        print(e.status, e.message)
    except bojstat.BojUnavailableError as e:
        # STATUS=503（DB アクセスエラー）
        print(e.status, e.message)
    except bojstat.BojTransportError as e:
        # ネットワーク接続エラー・タイムアウト
        print(e)
    except bojstat.BojValidationError as e:
        # 送信前バリデーションエラー
        print(e.validation_code, e)
```

例外の一覧:

| STATUS | 例外クラス | 説明 |
|:---|:---|:---|
| 400 | `BojBadRequestError` | パラメータ誤り |
| 500 | `BojServerError` | 予期しないエラー |
| 503 | `BojUnavailableError` | DB アクセスエラー |
| — | `BojGatewayError` | 上流ゲートウェイの非 JSON 応答 |
| — | `BojTransportError` | ネットワーク接続・タイムアウト |
| — | `BojValidationError` | 送信前バリデーション |
| — | `BojDateParseError` | DATE 解析失敗 |
| — | `BojConsistencyError` | 整合性検証エラー |
| — | `BojPaginationStalledError` | ページング停止 |
| — | `BojResumeTokenMismatchError` | 再開トークン不一致 |

### エラー分類

`MESSAGEID` からエラーの意味カテゴリを判定できます。

```python
from bojstat import BojClient

with BojClient() as client:
    result = client.errors.classify(status=400, message_id="M181005E")
    print(result.category)    # "invalid_db"
    print(result.confidence)  # 1.0
```

## リトライ

通信エラー（タイムアウト、接続エラー）および STATUS 429/500/503 は、指数バックオフで自動リトライされます（デフォルト最大 5 回）。

```python
from bojstat import BojClient

# リトライ設定のカスタマイズ
client = BojClient(
    retry_max_attempts=3,      # 最大試行回数（デフォルト: 5）
    retry_base_delay=1.0,      # バックオフ基準秒（デフォルト: 0.5）
    retry_cap_delay=16.0,      # バックオフ上限秒（デフォルト: 8.0）
)

# リトライ無効化
client = BojClient(retry_max_attempts=1)
```

## レート制限

高頻度アクセスによる接続遮断を防ぐため、デフォルトで 1 秒あたり 1 リクエストのレート制限が適用されます。

```python
client = BojClient(
    rate_limit_per_sec=0.5,  # 2 秒に 1 回
)
```

## タイムアウト

デフォルトのタイムアウトは 30 秒です。

```python
from bojstat import BojClient

client = BojClient(timeout=60.0)  # 60 秒に変更
```

## 言語と出力形式

```python
from bojstat import BojClient, Lang, Format

# 英語 + JSON（デフォルト: 日本語 + JSON）
client = BojClient(lang=Lang.EN, format=Format.JSON)

# リクエスト単位での上書きも可能
frame = client.data.get_by_code(
    db="FM08",
    code="FXERD01",
    lang="en",         # このリクエストだけ英語
)
```

## CLI

`bojstat-py[cli]` をインストールすると、コマンドラインから直接データを取得できます。

```sh
# メタデータを JSON で保存
bojstat metadata --db FM08 --out meta.json

# コード API で取得して CSV に保存
bojstat code --db CO --code TK99F1000601GCQ01000 --start 202401 --out data.csv

# 階層 API で取得して Parquet に保存
bojstat layer --db BP01 --frequency M --layer "1,1,1" --start 202504 --out data.parquet
```

## HTTP クライアントのカスタマイズ

内部の [httpx](https://www.python-httpx.org/) クライアントを直接指定できます。

```python
import httpx
from bojstat import BojClient

# プロキシ経由
client = BojClient(proxy="http://my.proxy:8080")

# HTTP/2 有効化（pip install 'httpx[http2]' が必要）
client = BojClient(http2=True)

# 外部 httpx.Client を注入
http_client = httpx.Client(
    base_url="https://www.stat-search.boj.or.jp/api/v1",
    timeout=60.0,
)
client = BojClient(http_client=http_client)
```

## HTTP リソースの管理

デフォルトでは、`close()` を呼ぶか、コンテキストマネージャを使用して HTTP 接続を解放します。

```python
from bojstat import BojClient

# コンテキストマネージャ（推奨）
with BojClient() as client:
    frame = client.data.get_by_code(db="CO", code="TK99F1000601GCQ01000")

# 手動クローズ
client = BojClient()
try:
    frame = client.data.get_by_code(db="CO", code="TK99F1000601GCQ01000")
finally:
    client.close()
```

非同期版:

```python
async with AsyncBojClient() as client:
    ...

# または
client = AsyncBojClient()
try:
    ...
finally:
    await client.aclose()
```

## 高度な設定

### 整合性モード

大量ページング中にサーバー側データが更新された場合の挙動を制御します。

```python
from bojstat import BojClient, ConsistencyMode

# strict: 不整合検知時に例外（デフォルト）
client = BojClient(consistency_mode=ConsistencyMode.STRICT)

# best_effort: 警告化して継続
client = BojClient(consistency_mode=ConsistencyMode.BEST_EFFORT)
```

### コード自動分割

250 件を超える系列コードを自動的にチャンク分割してリクエストします。

```python
client = BojClient(
    strict_api=False,         # strict モードを無効化
    auto_split_codes=True,    # 自動分割を有効化
)

# 250 件以上のコードを一度に指定可能
frame = client.data.get_by_code(
    db="FF",
    code=large_code_list,  # 500 件以上でも OK
)
```

### レスポンスメタ情報

すべてのレスポンスには `meta` 属性が付属し、API の処理結果情報を参照できます。

```python
frame = client.data.get_by_code(db="CO", code="TK99F1000601GCQ01000")

print(frame.meta.status)          # 200
print(frame.meta.message_id)      # "M181000I"
print(frame.meta.message)         # "正常に終了しました。"
print(frame.meta.date_parsed)     # datetime オブジェクト
print(frame.meta.request_url)     # 実行された URL
print(frame.meta.next_position)   # 次回検索開始位置（None なら全取得済み）
print(frame.meta.resume_token)    # 再開トークン
```

## 動作要件

Python 3.12 以上。
