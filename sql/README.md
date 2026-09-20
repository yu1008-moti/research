# `sql/`

リポジトリ内の手書き `.sql` ファイルを、パイプライン段階ごとにまとめたディレクトリ。
以前は `db/sql/` や `scripts/datap/graph/sql/` などに分散していたものをここに集約している。

| ディレクトリ | 役割 | 実行主体 |
|:-|:-|:-|
| [`synthesis/`](synthesis/) | 生テーブル（`db/duckdb`）→ `synthesis.imp.*` の中間テーブル・特徴量ビューへの変換 | 手動実行（DuckDB CLI等） |
| [`graph/`](graph/) | `synthesis.duckdb` からグラフ構築用データを取得・`graph_info_*.duckdb` へ投入するクエリ | `scripts/datap/graph/sql.py`（`fetch.*`/`insert.*`/`create.*`） |

- `sql/graph/` 配下のファイルパスは `scripts/datap/graph/cons.py` の `rel_sql` クラスに集約されている。
  ファイルを追加・移動する場合は、まず `rel_sql` の該当定数を更新すること。
- 各ファイルの詳細な処理内容は [`synthesis/_description.md`](synthesis/_description.md) を参照。
- `graph_lab/sql/archive/` には、`sql/graph/` の元になった初期の試作クエリ（現在は不使用）を参考用に残してある。
