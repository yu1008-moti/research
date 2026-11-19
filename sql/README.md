# `sql/`

リポジトリ内の手書き `.sql` ファイルを、パイプライン段階ごとにまとめたディレクトリ。
以前は `db/sql/` や `scripts/datap/graph/sql/` などに分散していたものをここに集約している。

| ディレクトリ | 役割 | 実行主体 |
|:-|:-|:-|
| [`synthesis/`](synthesis/) | 生テーブル（`db/duckdb`）→ `synthesis.imp.*` の中間テーブル・特徴量ビューへの変換 | 手動実行（DuckDB CLI等） |
| [`graph/`](graph/) | 旧・週次のグラフ構築用クエリ（`get_table_to_*.sql` 等）。再構築後も `db_connect.week` が参照 | `scripts/datap/graph/db_connect.py`（`week.get_table`） |
| [`graph_v2/`](graph_v2/) | 新・日次の取得クエリ（`fetch_*.sql`）とラベル検討（`get_y.sql.md`） | `scripts/datap/graph/db_connect.py`（`day.get_table`） |

- SQL は `string.Template` で `$START_DATE`/`$END_DATE` が展開される想定（現状 `graph_v2/` の一部は小文字 `$start_date` のままで不整合。詳細は [`claude_output/graph_spec.md`](../claude_output/graph_spec.md) §7）。
- 各ファイルの詳細な処理内容は [`synthesis/_description.md`](synthesis/_description.md) を参照。
- `graph_lab/sql/archive/` には、`sql/graph/` の元になった初期の試作クエリ（現在は不使用）を参考用に残してある。
