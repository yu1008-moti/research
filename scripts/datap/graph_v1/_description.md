# graph モジュールの概要

`scripts/datap/graph/` は、株価・財務データから **時系列グラフ（動的グラフ）** を構築するためのモジュール群である。
企業（Firm）ノードと財務資料（Fin）ノードを対象に、週次で以下 4 種類のエッジ行列を構築する。

| 種別 | 方向 | 意味 |
| --- | --- | --- |
| `Sp_Mat_firm2firm` | 空間 | 同一週内での企業間の関連（CAPM 残差リターンのローリング相関が閾値超え） |
| `Sp_Mat_fin2firm` | 空間 | 同一週内での財務資料の開示有無（対角成分に開示フラグ） |
| `Tm_Mat_firm2firm` | 時間 | 前週 → 当週の企業ノードの接続（価格データの存在有無） |
| `Tm_Mat_fin2fin` | 時間 | 過去の開示週 → 当週の財務資料ノードの接続 |

エントリポイントは `scripts/construct_graph.py` の `construct_graph()`。
`graph.pkl` が既に存在すればそれをロードし、無ければ構築して `edge_matrix/store/` に保存する。

---

## ディレクトリ構成

```text
scripts/datap/graph/
├── cons.py                     … 定数定義（パス・期間・ハイパーパラメータ・表示色）
├── sql.py                      … DuckDB からの価格 / 財務データ取得
├── _description.md             … 本ファイル
└── edge_matrix/
    ├── element.py              … ノード集合を表す NodeSet クラス
    ├── spacial.py              … 空間エッジ行列クラス SpacialEdgeMatrix（保持・参照・可視化）
    ├── temporal.py             … 時間エッジ行列クラス TemporalEdgeMatrix（保持）
    ├── constructor/
    │   ├── spacial_c.py        … 空間エッジ行列の構築ロジック（Spacial クラス）
    │   ├── temporal_c.py       … 時間エッジ行列の構築ロジック（Temporal クラス）
    │   └── utils.py            … 進捗表示など構築共通ヘルパー（u_common）
    ├── store/                  … 構築成果物の保存先（graph.pkl / returns_residual_matrix.parquet）
    └── ini_store_escape/       … store の初期成果物の退避コピー（再構築時のフォールバック用）
```

---

## 各スクリプトの詳細

### `cons.py`

モジュール全体で共有する定数を 3 つのクラスにまとめている。

- **`related_fetch`** … データ取得に関する定数。
  - `PATH_DB` : 参照する DuckDB ファイル（`./db/synthesis/synthesis.duckdb`）
  - `PATH_SQL_TO_FETCH_PRICES` / `PATH_SQL_TO_FETCH_FINANCIALS` : 実行する SQL ファイルのパス
  - `YEAR_START` / `YEAR_END` : 取得対象の年範囲（2011〜2025）
- **`train_constants`** … グラフ構築・学習データ生成のハイパーパラメータ。
  - `RESIDUAL_STORED_PATH` / `GRAPH_STORED_PATH` : 中間・最終成果物の保存パス
  - `TRAIN_START_YEAR` (2015), `ROLLING_WINDOW` / `WINDOW_SIZE` (52週), `THRESHOLD` (0.7 : 相関エッジの閾値)
  - `FIRST_WEEK_ID` (201501 : この週 ID 以降のみエッジを保持)
  - `DEVICE` : CUDA が利用可能なら `"cuda"`、それ以外は `"cpu"`
- **`print_constants`** … 進捗表示に使う ANSI エスケープシーケンス（色・行クリア）。

### `sql.py`

DuckDB へ接続してデータフレームを取得する `fetch` クラス（すべて `@staticmethod`）。

- `_any(QUERY)` : 任意の SQL 文字列を実行し `pd.DataFrame` を返す内部ヘルパー。接続は都度 open/close。
- `prices()` : `PATH_SQL_TO_FETCH_PRICES` を読み込み、`string.Template` で年範囲（`YEAR_START*100` 〜 `(YEAR_END+1)*100`、`YYYYWW` 形式の week_id 境界）を埋め込んで実行。CAPM 計算用の価格テーブルを返す。
- `financials(registered_nodes)` : `PATH_SQL_TO_FETCH_FINANCIALS` を読み込み、登録済み企業コード一覧を埋め込んで実行。週次の財務開示データを返す。

### `edge_matrix/element.py`

グラフの軸（ノードの並び）を管理する **`NodeSet`** クラス。

- コンストラクタ : `node_order` (`pd.Index` : ノード ID の並び) と `node_type` (`"Firm"` / `"Fin"` など) を保持。
- `rename_nodes_with_alias()` : 各ノード ID に `_{node_type}` を付与し、Firm 軸と Fin 軸を区別できるようにする（エッジ行列の生成時に呼ばれる）。
- `get_idx_corresponding_node_id(node_id)` : ノード ID から行 / 列インデックスを取得。未登録や重複時は `None`。

### `edge_matrix/spacial.py`

構築済みの空間エッジ行列を保持・参照・可視化する **`SpacialEdgeMatrix`** クラスと、内部ヘルパー `_utils`。

- コンストラクタ : `spacial_node2node_edge_list`（`(week_id, 疎テンソル)` のリスト。week_id 昇順）と縦軸・横軸の `NodeSet` を受け取り、両軸にエイリアスを付与して保持。
- `_utils._binary_Search_edge_matrix(week_id, list)` : week_id をキーに二分探索でエッジ行列を取得。
- `_utils.uniform_layout(G, ...)` : `networkx` グラフのノードを均一配置するレイアウト（spring layout を反復調整。出典コメントあり）。
- `get_nums_of_edges(week_id, node_id)` : 指定週・指定ノードの接続本数（非ゼロ要素数）を返す。
- `visualize_graph(week_id, node_id, radius=4)` : 指定週の隣接行列から `networkx` グラフを生成し、指定ノードの ego グラフ（半径 `radius`）を `matplotlib` で描画。対象ノードは赤、接続エッジはオレンジで強調し、隣接ノード一覧を print する。

### `edge_matrix/temporal.py`

構築済みの時間エッジ行列を保持する **`TemporalEdgeMatrix`** クラス。

- コンストラクタ : `temporal_previous2current_edge_list`（`(previous_week_id, current_week_id, 疎テンソル)` のリスト）と縦軸・横軸の `NodeSet` を受け取り、両軸にエイリアスを付与して保持。
- 現状は保持のみで参照・可視化メソッドは未実装。

### `edge_matrix/constructor/spacial_c.py`

空間エッジ行列を実際に構築する **`Spacial`** クラスと、2 つの内部ヘルパークラス。

- **`_utils_firm2firm`**（企業 – 企業エッジ）
  - `_rolling_capm_residual(stock_ret, market_ret, window=52)` : `statsmodels` の `RollingOLS` で CAPM を週次ローリング推定し、残差リターンとベータ系列を返す。
  - `_add_capm_factors_column(fetched_prices, window_size_for_capm)` : 全銘柄について CAPM 残差・ベータを計算し、`week_id × Code` の残差行列にピボットして `returns_residual_matrix.parquet` に保存。ファイルが既存ならスキップしてロード。窓長に満たない銘柄は除外し、除外率・有効銘柄数を print。
  - `_iter_prices_adjacent_matrix(returns_residual_matrix, window_size_for_corr, residuals_threshold, device)` : 残差行列に対し、和・グラム行列を差分更新しながらローリング相関行列を計算するジェネレータ。対角を 0 にし、`|corr| > threshold` のみ残して疎テンソル `(進捗率, week_id, 疎行列)` を yield。
- **`_utils_firm2fin`**（企業 – 財務資料エッジ）
  - `_get_financials_exists_matrix(financials_pivoted, registered_codes)` : 財務開示区分（`1Q`/`2Q`/`3Q`/`FY`）を数値化し、未登録銘柄列を補完した `week_id × Code` の開示有無行列を返す。
  - `_construct_fin_graph(exists_finsummary_df, weekid_list, device, registered_codes)` : 週ごとに対角成分へ開示フラグを立てた疎テンソルを yield するジェネレータ。
- **`Spacial`** クラス
  - コンストラクタ : `threshold` / `window_size_for_capm` / `window_size_for_corr` / `first_week_id` を受け取り（既定値は `train_constants`）、構築結果を溜めるリストを初期化。
  - `register_firm2firm_edge()` : `fetch.prices()` → CAPM 残差行列 → ローリング相関 → `first_week_id` 以降を `spacial_firm2firm_edge_list` に蓄積し、`SpacialEdgeMatrix` を返す。副作用として `firm_id_order`（残差計算後に確定する有効銘柄の並び）を設定。
  - `register_fin2firm_edge()` : `fetch.financials()` → 開示有無行列 → 週次疎テンソルを `spacial_fin2firm_edge_list` に蓄積し、`SpacialEdgeMatrix` を返す。縦軸 `Fin` / 横軸 `Firm`。

### `edge_matrix/constructor/temporal_c.py`

時間エッジ行列を構築する **`Temporal`** クラスと、2 つの内部ヘルパークラス。

- **`_utils_firm2firm._iter_temporal_firm2firm_matrix(firm_prices_exists_matrix, device, firm_id_order)`**
  前週と当週の両方で価格データが存在する銘柄の対角成分を 1 とした疎テンソルを、`(進捗率, previous_week_id, current_week_id, 疎行列)` として yield。
- **`_utils_fin2fin._iter_temporal_fin2fin_matrix(fin_report_exists_matrix, device, firm_id_order)`**
  財務開示行列を「開示があった週 ID」に変換し、`ffill().shift()` で直近の過去開示週を各当週に対応付ける。対角成分に「過去の開示週 ID」を格納した疎テンソルを `(進捗率, None, current_week_id, 疎行列)` として yield。
- **`Temporal`** クラス
  - コンストラクタ : `Spacial` の構築結果（`spacial_firm2firm_edge_list` / `spacial_fin2firm_edge_list` / `firm_id_order` / `result_fetched_prices` / `result_fetched_financials`）と `first_week_id` を受け取る。
  - `register_firm2firm_edge()` : 価格の存在有無行列（`AdjO` をピボット）から時間方向の企業間エッジを構築し、`TemporalEdgeMatrix` を返す。
  - `register_fin2firm_edge()` : 未実装（`pass`）。
  - `register_fin2fin_edge()` : 開示区分（`CurPerType`）のピボットから時間方向の財務資料エッジを構築し、`TemporalEdgeMatrix` を返す。`previous_week_id` は `0` 固定で格納（実際の過去週 ID は行列の対角成分に入る）。

### `edge_matrix/constructor/utils.py`

構築処理で共通利用する表示ヘルパー **`u_common`**（すべて `@staticmethod`）。

- `display_iter(Task_Summary, week_id=None, procssing_ratio=None, sparse_Node2Node_edge_matrix=None)` : `\r` で行を上書きしながら、タスク名・週 ID・グラフ形状・非ゼロ要素数（NNZ）・進捗率を色付きで表示。`procssing_ratio == 1.0` で改行。
- `display_note(note_title, content)` : タイトル付きの注記を 1 行 print。

### `edge_matrix/store/`

構築成果物の保存先。

- `returns_residual_matrix.parquet` : CAPM 残差リターンの `week_id × Code` 行列（`spacial_c.py` が生成）。
- `graph.pkl` : `(Sp_Mat_firm2firm, Sp_Mat_fin2firm, Tm_Mat_firm2firm, Tm_Mat_fin2fin)` のタプルを pickle 化したもの（`construct_graph.py` が生成／再利用）。
- `.gitkeep` : 空ディレクトリ保持用。

### `edge_matrix/ini_store_escape/`

`store/` の初期成果物を退避したコピー置き場。`construct_graph.py` の scratch モードで `store/` を削除・再構築する際のフォールバック／比較用に手動で保持しているもの。

---

## データフロー（`scripts/construct_graph.py`）

```text
construct_graph(threshold, window_size_for_capm, window_size_for_corr, first_week_id, scratch=False)
  │
  ├─ scratch=True                     … store/ の graph.pkl・residual.parquet を確認のうえ削除
  │
  ├─ graph.pkl が存在する             … pickle.load して 4 つのエッジ行列を返す（型チェックあり）
  │
  └─ graph.pkl が存在しない
        ├─ Spacial(...).register_firm2firm_edge()   → Sp_Mat_firm2firm
        │     （fetch.prices → CAPM 残差 → ローリング相関）
        ├─ Spacial(...).register_fin2firm_edge()    → Sp_Mat_fin2firm
        │     （fetch.financials → 開示有無行列）
        ├─ Temporal(Spacial の結果).register_firm2firm_edge()  → Tm_Mat_firm2firm
        ├─ Temporal(Spacial の結果).register_fin2fin_edge()    → Tm_Mat_fin2fin
        └─ 4 つをまとめて graph.pkl に pickle.dump
```
