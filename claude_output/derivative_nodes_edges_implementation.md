# オプション・先物ノード/エッジ追加 実装報告

対象ブランチ: `recreate_graph_modules`
対象ディレクトリ: `scripts/datap/graph/`

`data_pipeline.py` は従来、株式（`stock`）と決算情報（`statement`）のみをノードとして
登録できる仕様だった。本対応では、これに加えてオプション（`option`）・先物（`future`）を
新たなノードタイプとして追加し、以下6種類のエッジを新設した。

| # | 関係 | 意味 |
|---|---|---|
| 1 | `Option__corr__Option` | 同一原資産のオプション契約同士の相関エッジ |
| 2 | `Future__corr__Future` | 同一商品区分の先物契約同士の相関エッジ |
| 3 | `Stock__derivative__Option` | 銘柄 → その原資産とするオプション契約 |
| 4 | `Stock__derivative__Future` | 銘柄 → 主要な株価指数先物（新設の `derivative` エッジタイプ） |
| 5 | `Option__prev__Option` | 同一オプション契約の週次時系列エッジ |
| 6 | `Future__prev__Future` | 同一先物契約の週次時系列エッジ |

---

## 1. 事前調査で判明した事実

- 元DB（`db/synthesis/synthesis.duckdb`）には `imp.drv_opt_tmp`（オプション）・
  `imp.drv_ftr`（先物）が既に整形済みテーブルとして存在し、`imp.eqt_main`（株式）と
  同じ「週次集約前の日次バー」という形式だった。
- オプション側は `UndSSO` 列（4桁の個別株コード）で原資産に紐付け可能。ただし
  `ProdCat = EQOP`（個別株オプション）のみで、`NK225E`（日経225オプション）・
  `TOPIXE`（TOPIXオプション）・`JGBLFE`（債券オプション）は `UndSSO = '-'` で
  原資産の個別株が存在しない。
- `UndSSO` は `eqt_main.Code`（5桁、末尾0埋め）と末尾に `'0'` を付与することで
  一致することを実データで確認（サンプル2000件中240件が完全一致）。
- 先物側（`imp.drv_ftr`）は全て指数・債券・通貨先物（`NK225F`, `TOPIXF`, `JGBLF`,
  `REITF`, `USDJPYF` 等）であり、**個別株に対応する先物は存在しない**。また
  `imp.drv_ftr` には商品区分 `ProdCat` 列が残っていないため、`raw.drv_ftr`
  （`Code` は商品区分に対して不変）から別途引く必要があった。
- オプションは全期間で約27万契約が存在し、1原資産あたり最大3,674契約
  （平均約1,050契約）に達する。この規模が後述のパフォーマンス問題の原因になった。

これらを踏まえ、実装前にユーザーへ3点確認し、以下の方針で合意を得た。

| 論点 | 決定 |
|---|---|
| `Option__corr__Option` の相関範囲 | 同一原資産（`UndSSO`）内のみ |
| `Future__corr__Future` の相関範囲 | 同一商品区分（`ProdCat`）内のみ |
| `Stock__derivative__Future` の定義 | 全対象銘柄を主要な株価指数先物（`NK225F`・`TOPIXF`）の期近物に一律接続する "market backbone" 構造 |

---

## 2. 追加・変更したファイル

### 新規ファイル

| ファイル | 内容 |
|---|---|
| `scripts/datap/graph/derivative_corr.py` | オプション/先物のピアグループ内相関エッジを計算するモジュール（後述） |
| `scripts/datap/graph/sql/get_table_to_option.sql` | `imp.drv_opt_tmp` を週次集約し `option` ノード用DataFrameを作るクエリ |
| `scripts/datap/graph/sql/get_table_to_future.sql` | `imp.drv_ftr` を週次集約し `future` ノード用DataFrameを作るクエリ（`raw.drv_ftr` から `ProdCat` をJOIN） |

### 変更ファイル

| ファイル | 変更内容 |
|---|---|
| `scripts/datap/graph/data_pipeline.py` | 後述（本対応のメイン変更） |
| `scripts/datap/graph/sql.py` | `fetch.options()` / `fetch.futures()` を追加。加えて `graph_v2` を参照していた壊れたimportを修正（後述） |
| `scripts/datap/graph/cons.py` | 新規SQLファイルのパス定数を追加。加えて `graph_v2` パスのバグを修正 |
| `scripts/datap/graph/main.py` | `graph_v2` importのバグを修正 |

---

## 3. `data_pipeline.py` の主な変更点

### 3.1 定数

- `CATEGORICAL_COLUMNS` に `option: ["ProdCat", "UndSSO", "CM"]`、
  `future: ["ProdCat", "CM"]` を追加（`UndSSO` はNULL値も1つのカテゴリとして扱われる）。
- `REVERSE_RELATIONS` に `("stock","derivative","option") -> "rev_derivative"`、
  `("stock","derivative","future") -> "rev_derivative"` を追加。既存の `rev_report`
  と同じ仕組みで、`_build_full_graph()` が自動的に逆方向エッジを生成する。
- `MARKET_INDEX_FUTURE_PRODCATS = ["NK225F", "TOPIXF"]` を新設。
  `stock_derivative_future_preprocess()` が参照する。

### 3.2 `preprocess` クラス

- コンストラクタに `options_df` / `futures_df` を追加し、`unique_week_id` の
  集計対象にも含めた。
- 新設メソッド（すべて既存の `stock_corr_stock_preprocess` /
  `statement_prev_statement_preprocess` 等と同じ「`insert.edge()` へ
  DataFrameをまとめて渡す」パターンに準拠）:
  - `option_corr_option_preprocess()` / `future_corr_future_preprocess()`
    — `derivative_corr.build_peer_corr_edges()` を呼び出し、結果を
    共通ヘルパー `_insert_peer_corr_edges()` でDB登録する。
  - `option_prev_option_preprocess()` / `future_prev_future_preprocess()`
    — 共通ヘルパー `_prev_chain_preprocess()`（後述のベクトル化版）を呼び出す。
  - `stock_derivative_option_preprocess()`
    — `UndSSO` が非NULLの行を、実在する `(week_id, Code)` の株価データにのみ
    inner joinしてエッジ化（`statement_report_stock_preprocess` と同じ
    ダングリングエッジ対策パターン）。
  - `stock_derivative_future_preprocess()`
    — `MARKET_INDEX_FUTURE_PRODCATS` に該当する先物を `SQRemainingDays`
    が非負で最小（＝期近物）のものに週・商品区分ごとに絞り込み、
    その週の全 `is_target` 銘柄（`Mkt in {'0000','0500'}`）と直積で接続する。
- `node_id_define()` / `build_category_vocabs()` / `node_feats_define()` の
  `using_df_list` に `(options_df, "option")` / `(futures_df, "future")` を追加。
  これらの関数はnode_type非依存の汎用実装だったため、リストに追加するだけで
  option/futureノードの登録・vocab構築・特徴量登録が動く。
- `insert_to_graph_info_table()` の `edge_func_list` に6関数すべてを追加。

### 3.3 `graphDataSet` / `get_loaders()`

- `_ensure_db_built()` が `fetch.options()` / `fetch.futures()` を取得して
  `preprocess` に渡すよう変更。
- `_build_full_graph()` のノード読み込みループを
  `["stock", "statement"]` → `["stock", "statement", "option", "future"]` に拡張
  （エッジ側は元々 `edge_type` 文字列を `"__"` で汎用パースする実装だったため無変更）。
- `get_loaders()` の `num_neighbors` デフォルト辞書に、新設6関係＋その逆エッジ
  （計12エントリ）を追加。

---

## 4. `derivative_corr.py` の設計

`capm_corr.py`（株式のCAPM残差相関）とは異なる方式を採用した。

- デリバティブ契約は満期のある短命なインスタンスであり、「何と比較すべきか」が
  銘柄のように単一の市場ポートフォリオでは定義できないため、CAPM残差ではなく
  **同一グループ（`UndSSO` または `ProdCat`）内の生の週次収益率**（対数終値の差分）
  のローリング相関を採用。
- 契約寿命が株式（52週窓）よりずっと短いため、既定のローリング窓は
  `WINDOW_SIZE_FOR_CORR = 8`週、`MIN_PERIODS = 4`週、`THRESHOLD = 0.7`
  （`peer_corr_constants` としてモジュール内で調整可能）。

---

## 5. 実装中に発見・修正したバグ

コードを書いて終わりにせず、実データ（週範囲を絞った統合テスト）で
最後まで動かして検証した結果、以下2件の実害あるバグを発見し修正した。

### 5.1 ダングリングエッジ（存在しないノードを指すエッジ）

**症状**: `future__corr__future` エッジが `future_202307_168020019` という
存在しないノードを指しており、`graphDataSet._build_full_graph()` が
`KeyError` で失敗した。

**原因**: `build_peer_corr_edges()` の相関計算窓で、「直近`window`週で
`min_periods`週以上データがある契約」を対象契約として選んでいたが、これは
「窓内のどこかでデータがあった」ことしか保証せず、「**今週**ノードが実在するか」
は見ていなかった。そのため、直近数週間データが欠けている契約
（例: 上場廃止直後）に対しても、過去の窓内データを根拠にエッジを生成してしまい、
存在しないノードを指すダングリングエッジになっていた。

**修正**: `ret`列（`diff()`の都合で契約の初登場週は必ずNaNになる）とは別に、
「その週に実際に行が存在するか」を示す `exists` テーブルを追加し、
`active_cols` の選定条件に `exists.iloc[t]` を追加した
（`derivative_corr.py` 92-107行目）。

### 5.2 `option_prev_option_preprocess` の性能問題（約30分 → 数秒）

**症状**: 週範囲を20週に絞った統合テストにおいてすら、
`option_prev_option_preprocess` の実行に **約30分** かかった
（全期間・約27万契約では実用不可能な時間になる見込み）。

**原因**: 初期実装は既存の `statement_prev_statement_preprocess` と同じ
「契約コードごとにPythonループを回し、`DataFrame`をフィルタし、
1コードにつき1回 `insert.edge()`（＝DuckDB接続を1回張り直す）」という
パターンを流用していた。この方式は銘柄（約4,000コード）や決算
（約3,000コード）では許容範囲だったが、20週の範囲だけでも約3万契約が
存在するオプションでは、`O(契約数 × 行数)` のフィルタ処理と
`3万回のDB接続オーバーヘッド`が支配的になり破綻した。

**修正**: `_prev_chain_preprocess()` を `groupby("Code")["week_id"].shift(1)`
による完全ベクトル化 + 単一のバルク `insert.edge()` 呼び出しに書き換えた
（`data_pipeline.py` 444-480行目）。修正後、同じ20週範囲のテストで
`option_prev_option_preprocess` は数秒で完了した。

---

## 6. 動作確認

実データ（`db/synthesis/synthesis.duckdb`）を用い、週範囲を `202301〜202320`
（20週）に絞った一時DB（`serial_id=8888`、検証後に削除済み）で
パイプライン全体を実行し、以下を確認した。

1. `preprocess.insert_to_graph_info_table()` が全12関数（既存6＋新設6）を
   エラーなく完走すること。
2. 生成されたノード数・エッジ数が妥当であること:

   | node_type | 件数 |
   |---|---|
   | stock | 83,681 |
   | statement | 5,934 |
   | option | 273,567 |
   | future | 1,610 |

   | edge_type | 件数 |
   |---|---|
   | option__corr__option | 352 |
   | option__prev__option | 243,074 |
   | future__corr__future | 2,086 |
   | future__prev__future | 1,512 |
   | stock__derivative__option | 273,567 |
   | stock__derivative__future | 73,484 |

3. `edge`テーブルの `src_node_id` / `dst_node_id` がすべて `node`テーブルに
   存在すること（ダングリングエッジ0件）をSQLで直接検証。
4. `graphDataSet` が `HeteroData` を正しく構築できること
   （4ノードタイプ・12エッジタイプすべてが期待通りのテンソル形状で格納される）。
5. `get_loaders()` で作成した `NeighborLoader` から実際にバッチを1つ取得し、
   `stock`起点の2-hopサンプリングが `option`/`future`ノードまで
   正しく辿れること（逆エッジ `rev_derivative` 経由の逆方向メッセージパッシングも含む）。

---

## 7. 既存コードの副次的な修正（バグ）

`scripts/datap/graph/` 配下は元々 `graph_v2` という名前だったものを
リネームした形跡があるが、以下のパス文字列が `graph_v2` のまま残っており、
**新機能とは無関係に、そもそも `data_pipeline.py` がimportすらできない状態**
だった（`sql.py` が `scripts.datap.graph_v2.cons` を import しようとして
`ModuleNotFoundError` になる）。実データでの検証を行うために必須だったため、
本対応内で修正した。

| ファイル | 修正箇所 |
|---|---|
| `cons.py` | `PATH_GRAPHINFO_DB` / 各SQLファイルパス定数（`graph_v2` → `graph`） |
| `sql.py` | `from scripts.datap.graph_v2.cons import ...` → `graph.cons` |
| `data_pipeline.py` | `DEFAULT_VOCAB_DIR`、`get_loaders()` 内の `graphDataSet(root=...)` |
| `main.py` | `import scripts.datap.graph_v2.data_pipeline` → `graph.data_pipeline` |
| `capm_corr.py` | `capm_corr_constants.RESIDUAL_STORED_PATH`（後日の `graph_params` 統合作業で発覚・修正。詳細は§9参照） |

### 7.1 追記: `capm_corr.py` 側の同種バグは「importが通らない」だけでなく計算結果にも影響していた

上表のうち `capm_corr.py` の1件は、本報告の初版作成後（§9のパラメータ集約作業中）に
追加で発見したもの。`capm_corr_constants.RESIDUAL_STORED_PATH` が
`./scripts/datap/graph_v2/store/returns_residual_matrix.parquet` を指したままだった。

このパスは実在しないため `residual_matrix_from_prices()` の
`cache_path.exists()` は常に `False` を返し、**キャッシュが存在するはずの状況でも
毎回 `prices_df` から CAPM残差をゼロから再計算していた**。本報告§6の検証時
（週範囲を20週に絞ったテスト）ではこれが「52週ローリング窓を満たすのに
十分な期間が無い」状態を招き、`stock__corr__stock` エッジがかなり少なめに
出ていた（実測 79,458件）。パス修正後、同じ20週テストで
実在する `scripts/datap/graph/store/returns_residual_matrix.parquet`
（全期間分のキャッシュ）が正しく参照されるようになり、178,576件まで増加した
（＝修正前の値は過小だった）。§6の実測値表はこの修正**前**の値のままなので、
参考にする際は本節の内容を踏まえること。

---

## 8. 今後の調整ポイント

- 相関計算の窓幅・閾値・最小観測数、`MARKET_INDEX_FUTURE_PRODCATS` 等の
  ハイパーパラメータは §9 で `scripts/datap/graph/cons.py` の `graph_params`
  クラスに一元化した。個別ファイルの定数を直接編集するのではなく、
  そちらを参照・変更すること。
- `derivative_corr.py` のグループ内相関計算は、1グループ内の
  「同時生存契約数」が極端に多いケース（数百契約が同時に生存する原資産等）が
  もし将来出てきた場合は、`capm_corr.py` の差分更新（Gram行列の逐次更新）
  方式への切り替えを検討する余地がある旨をコード内コメントに残してある。

---

## 9. パラメータの一元化（`graph_params`）

ユーザーが調整し得るハイパーパラメータ・定数が `capm_corr.py`
（`capm_corr_constants`）、`derivative_corr.py`（`peer_corr_constants`）、
`data_pipeline.py`（モジュール直下の複数の定数）に分散していたため、
`scripts/datap/graph/cons.py` に新設した単一クラス `graph_params` に統合した。
既存の `rel_sql`（DBパス・SQLファイルパス・取得週範囲）とは役割を分け、
`graph_params` は**グラフ構築のハイパーパラメータ**専任とした。

### 9.1 統合した項目

| 旧定義 | 新定義（`graph_params`） | 意味 |
|---|---|---|
| `capm_corr.capm_corr_constants.WINDOW_SIZE_FOR_CAPM` | `CAPM_WINDOW_SIZE_FOR_CAPM` | CAPMローリング推定の窓（週） |
| `capm_corr.capm_corr_constants.WINDOW_SIZE_FOR_CORR` | `CAPM_WINDOW_SIZE_FOR_CORR` | CAPM残差相関の窓（週） |
| `capm_corr.capm_corr_constants.THRESHOLD` | `CAPM_THRESHOLD` | stock__corr__stock のしきい値 |
| `capm_corr.capm_corr_constants.FIRST_WEEK_ID` | `CAPM_FIRST_WEEK_ID` | エッジを返す最初の週ID |
| `capm_corr.capm_corr_constants.RESIDUAL_STORED_PATH` | `CAPM_RESIDUAL_STORED_PATH` | 残差行列キャッシュのパス（§7.1のバグ修正箇所） |
| `capm_corr.capm_corr_constants.DEVICE`（import時に即評価） | `CAPM_DEVICE`（既定`None`＝呼び出し時に自動判定） | 相関計算に使うdevice |
| `derivative_corr.peer_corr_constants.WINDOW_SIZE_FOR_CORR` | `DERIVATIVE_CORR_WINDOW_SIZE` | option/future相関の窓（週） |
| `derivative_corr.peer_corr_constants.MIN_PERIODS` | `DERIVATIVE_CORR_MIN_PERIODS` | 相関計算に必要な最小観測週数 |
| `derivative_corr.peer_corr_constants.THRESHOLD` | `DERIVATIVE_CORR_THRESHOLD` | option/future相関のしきい値 |
| `data_pipeline.MARKET_INDEX_FUTURE_PRODCATS` | `MARKET_INDEX_FUTURE_PRODCATS` | Stock__derivative__Future の接続先先物区分 |
| `data_pipeline.DEFAULT_VOCAB_DIR` | `DEFAULT_VOCAB_DIR` | vocab保存先ディレクトリ |
| `data_pipeline.TIME_ENCODING_EPOCH`（`pd.Timestamp`直書き） | `TIME_ENCODING_EPOCH`（文字列） | 時間エンコーディングの基準日 |
| `get_loaders()` 引数デフォルト `0.7`/`0.85`/`32` | `SPLIT_1_PER`/`SPLIT_2_PER`/`BATCH_SIZE` | train/val/test分割・バッチサイズ |
| `get_loaders()` 内の12関係分ハードコード辞書 `{(...): [10,10], ...}` | `NUM_NEIGHBORS_PER_HOP`/`NUM_HOPS` | NeighborLoaderの近傍サンプリング数 |

`data_pipeline.py` 側の `MARKET_INDEX_FUTURE_PRODCATS` / `DEFAULT_VOCAB_DIR` /
`TIME_ENCODING_EPOCH` はモジュール直下の同名変数として残してあるが、
中身は `graph_params` から取ってくるだけの薄いエイリアスになっている
（関数のデフォルト引数として使われている箇所を変更せずに済ませるため）。

### 9.2 `get_loaders()` の `num_neighbors` 辞書を動的生成に変更

従来は12関係すべてを手書きで列挙していたため、エッジ関係を追加・削除する
たびに書き忘れるリスクがあった。修正後は

```python
per_hop = [graph_params.NUM_NEIGHBORS_PER_HOP] * graph_params.NUM_HOPS
num_neighbors = {edge_type: per_hop for edge_type in data.edge_types}
```

のように、実際に構築されたグラフの `data.edge_types` から動的に辞書を作るよう
変更した。関係ごとに個別の値を与えたい場合（例: 第6章[heterodata_batch_output_explained.md](heterodata_batch_output_explained.md)
の懸念事項6.1で触れた `future, rev_derivative, stock` だけ絞る、等）は、
従来通り `get_loaders(num_neighbors={...})` で明示的に辞書を渡せば
この自動生成をバイパスして上書きできる。

### 9.3 値を変更する2通りの方法

1. **`cons.py` の `graph_params` クラスの値を直接書き換える**
   （恒久的にデフォルト値を変えたい場合）。
2. **各関数呼び出し時にキーワード引数で個別に上書きする**
   （その場限りで試したい場合。例:
   `derivative_corr.build_peer_corr_edges(options_df, group_col="UndSSO", threshold=0.5)`、
   `get_loaders(serial_id=9999, batch_size=64)` など）。

いずれの関数も「引数省略時は `graph_params` の値を使う」という設計になっているため、
上記どちらの方法でも同じ変更を実現できる。

### 9.4 動作確認

§6と同じ手順（週範囲を絞った実データでの一時DB構築）を本リファクタ後に再実行し、
以下を確認した。

- `preprocess.insert_to_graph_info_table()` が新パラメータ経由の関数呼び出しで
  問題なく完走すること。
- リファクタ後は §7.1 の修正により `stock__corr__stock` が178,576件
  （修正前は79,458件）になったこと以外、ノード数・他エッジ種別の件数に
  差異が無いこと。
- ダングリングエッジが引き続き0件であること。
- `graphDataSet`/`HeteroData`/`NeighborLoader`（動的生成した`num_neighbors`込み）
  が問題なく構築・サンプリングできること。
