# データ構築フロー仕様（再構築版・WIP）

対象: `scripts/datap/graph/`（2026-10-11 時点の作業ツリー）

旧パイプライン（`data_pipeline.py` / `capm_corr.py` / `derivative_corr.py` / `cons.py` / `sql.py`、
`graph_info_*.duckdb` 経由の `graph_node`/`graph_edge` 方式、`model/baseline/`）は破棄し、
ゼロから作り直している。本書は**現在の作業ツリーに実在するコードだけ**を記述する。
旧仕様は git 履歴（`git log -- claude_output/graph_spec.md`）を参照。

設計意図の備忘録は [`scripts/datap/graph/dscribe.md`](../scripts/datap/graph/dscribe.md)、
ラベル設計のメモは [`md/my_memo/labeling_memo.md`](../md/my_memo/labeling_memo.md) にある。

---

## 1. 全体フロー

```
synthesis.duckdb (db/synthesis/synthesis.duckdb, read_only)
   │  db_connect.{week|day}.get_table(name)      … SQL を Template 展開して実行 → DataFrame
   ▼
raw_stocks / raw_statements / raw_futures / raw_mkt_index   (pandas)
   │  MarketDataset.download() → preprocessing()
   │     ・mask_error_nodes   … 上場前の決算などを除外（予定）
   │     ・node_to_idx        … "<table>_<Code>_<week_id>" → 通し node_idx
   │     ・varchar_to_idx     … カテゴリ/文字列 → 整数（idx_share で複数列が語彙を共有）
   │     ・date_to_idx        … 日付 → 整数
   ▼
MarketDataset.pre_transform(data)     … HeteroData にノード特徴・エッジを書き込む
   │     stock_corr_stock / stock_report_statement / stock_madeup_index / index_derivative_future
   ▼
torch.save → <root>/processed/processed_market_data.pt   (InMemoryDataset)
   ▼
loader.py（NeighborLoader 用・未実装）
```

期間の既定値は `2000-01-01`〜`2026-12-31`（`db_connect.py` / `node_utils.py` / `dataset.py` に重複定義）。
学習に使う期間は 2010-01-01〜2025-12-31 の予定（`dscribe.md`）。

方針（`dscribe.md` より）: 生データは取得後、**ディスク保存前に**カテゴリ・文字列・日付を数値へ変換する
（torch 形式で保存するため）。カテゴリは有限集合で、評価期間中に新規値は出ない前提。

---

## 2. `db_connect.py` — DB → DataFrame

| 要素 | 内容 |
|---|---|
| `PATH_TO_ORIGIN_DB` | `./db/synthesis/synthesis.duckdb`（`read_only=True` で接続） |
| `_BaseTimeFrame.get_table(table_name)` | `TABLE_NAME_MAP[table_name]` の SQL を読み、`string.Template.substitute(START_DATE=, END_DATE=)` で展開して実行、`DataFrame` を返す。行数・列名を print する |
| `week` | 週次。`sql/graph/` の `get_table_to_CAPM.sql`(stocks) / `get_fin_data_by_week.sql`(statements) / `get_table_to_future.sql`(futures) / `get_table_to_market_index.sql`(mkt_index) |
| `day` | 日次。`sql/graph_v2/` の `fetch_stocks.sql` / `fetch_statements.sql` / `fetch_futures.sql` / `fetch_market_index.sql` |

テーブル名キーは `stocks` / `statements` / `futures` / `mkt_index` の4つ。

### `sql/graph_v2/`（日次・新）

| ファイル | 取得元 | 内容 |
|---|---|---|
| `fetch_stocks.sql` | `imp.eqt_main` | `TradeDate, Code`, 前場（`MAdj*`）・後場（`AAdj*`）調整後 OHLC・ストップ高安（推定）、`AdjVo, Mrgn, S33, S17, Mkt` |
| `fetch_statements.sql` | `imp.fin_sum` | `DiscDate AS TradeDate` + 他の全列 |
| `fetch_futures.sql` | `raw.drv_ftr` | `ProdCat='TOPIXF'` のみ。`Code = substring(CM,3,2) \|\| substring(Code,4,2)` |
| `fetch_market_index.sql` | `raw.idx_prc` | 指数コード（`0000` TOPIX、`0040`–`0060` 業種別、`0080`–`0090` 他）を抽出。`Code AS index_id` |
| `fetch_label.sql` / `get_y.sql.md` | `imp.eqt_main` | ラベル `y` 作成クエリの検討（下記 §6） |

---

## 3. `dataset.py` — `MarketDataset(InMemoryDataset)`

- 引数: `root='./pt'`, `time_frame_mode`（`'w'` 週次 / `'d'` 日次。それ以外は `download()` で `ValueError`）。
- `raw_dir = <root>/raw`、`processed_file_names = ['processed_market_data.pt']`。
- `download()` … `week`/`day` から4テーブルを取得し `preprocessing()` を呼ぶ。
- `preprocessing()` … 上述のマッピングを適用。モードごとに対象列が違う
  （週次: `Code, Mkt, S33, S17` / `CurPerType` / `UndSSO, CM_year, CM_month` / `CurFYEn`、
  日次: 各テーブルの `Code`・`TradeDate`・`CurFYEn`・`LTD`・`index_id` など）。
  `listed_stocks_by_time`（時点 → 上場銘柄 node_idx のリスト）も作る。
- `pre_transform(data)` … 下記 `preprocess/*` の `set_info` を呼んで `HeteroData` を埋める。
- `process()` … 空の `HeteroData` を作って `pre_transform` → `collate` → `torch.save`。

---

## 4. `preprocess/` — ノード・エッジ構築

### `node_utils.py`

| 名前 | 役割 |
|---|---|
| `node_to_idx` | 各 DataFrame に `"<table>_<Code>_<week_id>"` 形式のラベルを作り、全テーブル横断の一意な整数 `node_idx` に変換。`get_label_to_idx()` が `n2i_map` |
| `varchar_to_idx` | 列ごとの `{値: 整数}` 辞書。`idx_share={'alias': (列...)}` で複数列が同一辞書を共有 |
| `date_to_idx` | `date_range()`（`START_DATE`〜`END_DATE` の日付）に対する連番へ変換。範囲外は `-1` |
| `mask_error_nodes` | 上場週より前の決算・原資産上場前のオプションを除外する意図の関数 |
| `get_dict_of_listed_stocks_by_weekid` / `_by_trade_date` | 時点 → 上場銘柄 node_idx の辞書 |

### エッジ/ノード構築モジュール

| ファイル | 状態 | 内容 |
|---|---|---|
| `stock_corr_stock.py` | 実装済 | `RollingOLS`（窓52週）で CAPM 残差を作り、週×銘柄ピボットに対し Gram 行列を逐次更新して相関を計算、`\|corr\|>0.5` を `('stock','corr','stock')` に。`edge_attr`=相関、`observable`=週ID。`data['stock'].x/node_idx` もここで設定 |
| `stock_report_statement.py` | 実装済 | `statements` ノード特徴と `('stock','report','statement')` エッジ（`edge_attr=1`, `observable=week_id`） |
| `stock_madeup_index.py` | 途中 | 指数ノード `mkt_index` の特徴を書き込む骨格。`TPOIX_CODE='0000'` の定数あり |
| `index_derivative_future.py` | 空 | 指数 ↔ 先物エッジの予定地 |

---

## 5. `loader.py`

import 文のみ（スタブ）。`NeighborLoader` 設定は未実装。

---

## 6. ラベル設計（検討中）

`md/my_memo/labeling_memo.md` / `sql/graph_v2/get_y.sql.md`: 翌営業日リターン
`l1_DAdjC / DAdjC - 1` を求め、`Mkt in ('0000','0500','7000')` を対象に、
リターンの 1/3・2/3 分位（約 ±0.0063 付近）で **negative / neutral / positive の3クラス**に分ける案。
全体で各クラスほぼ 33.3% になることを確認済み（約766万行）。
`AdjVo = 0` や NaN/Inf のリターンは `is_valid=0` として除外する（`fetch_label.sql`）。

---

## 7. 既知の未完了・不整合（2026-10-11 時点）

書き直し作業中に見つけた、動かす前に直すべき点。

- `db_connect.py`: SQL 側のプレースホルダが `$start_date`/`$end_date`（`fetch_futures.sql` / `fetch_market_index.sql` / `fetch_statements.sql`）で、
  `Template.substitute(START_DATE=, END_DATE=)` のキーと大文字小文字が合わず `KeyError` になる。
  `fetch_stocks.sql` は `where` 直後に `and` があり構文エラー。
- `week.TABLE_NAME_MAP['mkt_index']` が指す `sql/graph/get_table_to_market_index.sql` は存在しない。
- `tests/test_db_connect.py` が呼ぶ `get_stocks_table()` 等は `db_connect` に存在しない（現行 API は `week/day.get_table`）。
- `dataset.py`: `import` している `preprocess` サブモジュールの `set_info` シグネチャと呼び出しが一致しない
  （`stock_madeup_index.set_info` は引数4つ必要、`stock_corr_stock.set_info` / `stock_report_statement.set_info` は `n2i_map` 前提で `week_id` 列を使うが日次テーブルには `week_id` が無い）。
  `node_to_idx` は `options_df` を要求するが `preprocessing()` は `raw_mkt_index` を渡している。
  `__init__` は `super().__init__` 内で `process` が走る前に `time_frame_mode` を設定していないため、`download()` が `self.time_frame_mode` を参照できない。
- `mask_error_nodes` は引数の DataFrame を再代入するだけで呼び出し元に反映されない（フィルタが効かない）。
- `stock_corr_stock.py`: `edge_indices[0]` と `[1]` に同一のマッピング（`stocks_<Code>_<week>`）を適用している。
  エッジの `edge_type` は `_calc_corr_matrix` が yield する `"corr"`。
- ハイパーパラメータ（窓52・閾値0.5・期間）は各ファイルに定数が散在。旧 `graph_params` 相当の集約先は未定。
