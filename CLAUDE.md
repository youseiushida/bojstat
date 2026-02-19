# コメントについて
Google StyleでDocstringを書いてください
日本語で書くこと

# 実装について
実装時には以下に示すように既存のファイルを参照すること。/src配下に.pyファイルがあります。/stubs配下に.pyiファイルがあります。バッチ処理系は/tools配下にあります。
.pyiでインターフェースを定義しているため、これを読むことで.pyファイルを読む場合に比べてコンテキストを圧縮できます。
- 既存バグの修正	.py (本体)	中身のロジックを見ないと直せないため。
- 新規機能の開発	.pyi (関連モジュール)	既存機能の「使い方」だけ分かれば十分なため。
- リファクタリング	.py + .pyi	インターフェースを維持したまま中身を書き換えるため。

# コマンドについて
.pyiの生成には以下のコマンドを使う
uv run stubgen src/bojstat --include-docstrings -o stubs
testには以下のコマンドを使う
uv run pytest
ruffには以下のコマンドを使う
uv run ruff check src tests
