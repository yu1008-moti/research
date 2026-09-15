# graph ライブラリ 関数レベル仕様書

対象ディレクトリ: `scripts/datap/graph/`

このドキュメントは以下6ファイルに定義される全関数・全メソッド・全クラスについて、
シグネチャ・引数・返り値・処理内容・前提条件（不変条件）・副作用をまとめたものである。

- [data_pipeline.py](#1-data_pipelinepy) — DB前処理 〜 HeteroData構築 〜 DataLoader生成のメインパイプライン
- [capm_corr.py](#2-capm_corrpy) — CAPM残差リターンに基づく銘柄間相関エッジの構築
- [derivative_corr.py](#3-derivative_corrpy) — オプション/先物のピアグループ内相関エッジの構築
- [cons.py](#4-conspy) — パス・パラメータ定数の定義（ハイパーパラメータは `graph_params` に一元化）
- [sql.py](#5-sqlpy) — DuckDBへのfetch/insert/create処理
- [main.py](#6-mainpy) — エントリポイント（現状スタブ）

> **旧 `graph_v2` からの改称に関する注記**: このディレクトリは元々 `scripts/datap/graph_v2/`
> という名前だったが、`graph` にリネームされた。リネーム後も一部のパス文字列
> （`cons.py`・`sql.py`・`main.py`・`data_pipeline.py` 内）が `graph_v2` を指したままになっており、
> **これらのパスに依存する箇所は一切動作しない状態だった**（`sql.py` の壊れたimportにより
> `data_pipeline.py` 自体がimportエラーになる、`capm_corr.py` のキャッシュパスが常にキャッシュ
> ミスして毎回残差を再計算する、等）。本ドキュメントが記述する現在の実装では、これらは
> 全て `graph` を指すよう修正済みである。

---

## 全体アーキテクチャ

```
① raw data (synthesis.duckdb)
      │  sql.fetch.prices() / sql.fetch.financials()
      │  sql.fetch.options() / sql.fetch.futures()
      ▼
② preprocess クラス（data_pipeline.py）
      │  ノード/エッジをDataFrame化し、graph_info_{serial_id}.duckdb に格納
      │  - node テーブル: node_id, is_target, ticker, node_type, time_id
      │  - edge テーブル: edge_id, edge_type, src_node_id, dst_node_id, edge_weight, observable_time_id
      │  - feats テーブル: node_id, feats(JSON: cont/cat/date), feats_num
      ▼
③ graphDataSet（InMemoryDataset）
      │  DBから全ノード・全エッジを読み出し、文字列node_idを整数indexに変換して
      │  単一の HeteroData を構築し、data_{serial_id}_full.pt として保存
      ▼
④ get_loaders()
      │  is_target かつ time_id の範囲でtrain/val/testをマスク分割し、
      │  NeighborLoader を3つ生成（グラフ自体は分割しない）
      ▼
⑤ 学習ループ（mock_code が疎通確認の例）
```

### ノードタイプ（4種類）

| node_type | 由来 | is_target | 備考 |
|---|---|---|---|
| `stock` | `sql.fetch.prices()`（`imp.eqt_main` の週次集約） | `Mkt in {"0000","0500"}` の場合 `True` | 予測対象。カテゴリ列: `S33,S17,Section_id,Mkt,Mrgn` |
| `statement` | `sql.fetch.financials()`（`imp.fin_sum`） | 常に `False` | カテゴリ列: `CurPerType`。日付列: `CurFYEn` |
| `option` | `sql.fetch.options()`（`imp.drv_opt_tmp` の週次集約） | 常に `False` | カテゴリ列: `ProdCat,UndSSO,CM` |
| `future` | `sql.fetch.futures()`（`imp.drv_ftr` の週次集約） | 常に `False` | カテゴリ列: `ProdCat,CM` |

### エッジタイプ（8つ＋自動生成される逆エッジ3つ）

| src | relation | dst | 意味 | 逆エッジ |
|---|---|---|---|---|
| stock | corr | stock | CAPM残差リターンのローリング相関 + 同一銘柄の週次連続エッジ | なし（対称のため相互登録） |
| statement | prev | statement | 同一銘柄の前期決算→今期決算 | なし |
| statement | report | stock | 決算→対応する銘柄週次ノードへの報告 | `stock, rev_report, statement` |
| option | corr | option | 同一原資産(UndSSO)のオプション契約同士のローリング相関 | なし（対称のため相互登録） |
| option | prev | option | 同一オプション契約の前週→今週 | なし |
| future | corr | future | 同一商品区分(ProdCat)の先物契約同士のローリング相関 | なし（対称のため相互登録） |
| future | prev | future | 同一先物契約の前週→今週 | なし |
| stock | derivative | option | 銘柄→その原資産とするオプション契約 | `option, rev_derivative, stock` |
| stock | derivative | future | 全対象銘柄→主要な株価指数先物の期近物 | `future, rev_derivative, stock` |

逆エッジの自動生成は `REVERSE_RELATIONS`（`data_pipeline.py`）による。`rev_report` と
`rev_derivative` は relation名としては共有されているが、`(src,rel,dst)` の3-tupleとしては
`(stock, rev_report, statement)` / `(option, rev_derivative, stock)` /
`(future, rev_derivative, stock)` のように dst/src の型が異なるため別々のエッジ種別として
`HeteroData` に格納される。

node_id / edge_id の命名規則:
- ノード: `{node_type}_{week_id}_{Code}` 例: `stock_202001_1301`, `option_202320_331035108`
- エッジ: `{src_type}__{relation}__{dst_type}_{...}` 例: `stock__corr__stock_202001_1301_1305`
  （`__` 区切りで `(src_type, relation, dst_type)` の3-tupleに一意パース可能）

---

## 1. data_pipeline.py

前回指摘事項を反映した書き直し版に加え、`option`/`future` ノードと6種類のデリバティブ関連
エッジを追加した現行版。モジュールdocstringに記載された主な変更点（旧版からの継続事項）:

1. train/val/testを物理ファイルで分けず、単一の HeteroData を1つだけ保存し、split はロード時にマスクで行う設計。
2. DB構築（raw data ingestion）と `.pt` 生成（グラフ構築）を別ステップに分離。
3. エッジタイプのキーを `"__"` 区切りの3-tupleとして一意にパースできるよう統一。
4. ノード特徴量 `x`、`is_target` マスク、`node_id` 文字列を HeteroData に正しく格納。文字列配列はNeighborLoaderがテンソル化できないため `.npy` に別保存。
5. `statement -> stock` の一方向エッジしか無かった問題を `REVERSE_RELATIONS` による逆エッジ自動生成で解消。
6. `get_dataloader` と `get_neighbor_loader` の二重バッチ化をやめ `get_loaders()` に統合。

### モジュール定数

以下の定数はいずれも `cons.py` の `graph_params` を参照するだけの薄いエイリアスであり、
値自体の定義は `graph_params` 側に一元化されている（詳細は[4. cons.py](#4-conspy)参照）。
関数のデフォルト引数として使われている箇所を変更せずに済ませるため、モジュール直下の
同名変数として残してある。

| 定数 | 型 | 内容 |
|---|---|---|
| `REVERSE_RELATIONS` | `Dict[Tuple[str,str,str], str]` | 逆エッジを自動生成する関係の指定。`("statement","report","stock") -> "rev_report"`、`("stock","derivative","option") -> "rev_derivative"`、`("stock","derivative","future") -> "rev_derivative"` の3件。対称な関係（相関エッジ等）はここに入れない。 |
| `MARKET_INDEX_FUTURE_PRODCATS` | `List[str]` | `= graph_params.MARKET_INDEX_FUTURE_PRODCATS`（既定 `["NK225F","TOPIXF"]`）。`Stock__derivative__Future` で全対象銘柄を接続する「主要な株価指数先物」の商品区分。 |
| `CATEGORICAL_COLUMNS` | `Dict[str, List[str]]` | `stock`: `["S33","S17","Section_id","Mkt","Mrgn"]` / `statement`: `["CurPerType"]` / `option`: `["ProdCat","UndSSO","CM"]` / `future`: `["ProdCat","CM"]`。ここに列挙した列のみEmbedding用の特殊扱いになる（`graph_params` には含まれず、ここに直書きされている。理由は下記コラム参照）。 |
| `DATE_COLUMNS` | `Dict[str, List[str]]` | `statement`: `["CurFYEn"]`。Time2Vec等に渡す日付列。 |
| `DEFAULT_VOCAB_DIR` | `str` | `= graph_params.DEFAULT_VOCAB_DIR`（既定 `"scripts/datap/graph/DS/vocab"`） |
| `TIME_ENCODING_EPOCH` | `pd.Timestamp` | `pd.Timestamp(graph_params.TIME_ENCODING_EPOCH)`（既定 `"2000-01-01"`）。日付→経過日数変換の基準日。 |
| `_SAFE_GLOBALS_REGISTERED` | `bool` | `_allow_numpy_globals_for_torch_load()` の多重登録防止フラグ（モジュールプライベート）。 |

> **`CATEGORICAL_COLUMNS`/`DATE_COLUMNS` を `graph_params` に含めていない理由**:
> これらは「スイープして良いハイパーパラメータ」ではなく、SQL側の出力列・
> `node_feats_define()` のJSON構造と密結合したスキーマ定義であるため、
> 単純な数値・文字列の調整パラメータとは性質が異なると判断し、`graph_params` の
> 対象範囲（ユーザーが値を変えて実験することを想定した知識）から意図的に除外している。

### 関数

#### `_allow_numpy_globals_for_torch_load() -> None`
- **概要**: `torch.load(weights_only=True)` が `HeteroData` 内の numpy 配列（node_str_id等）を復元できるよう、`numpy._core.multiarray._reconstruct`（または `numpy.core.multiarray._reconstruct`。numpyのバージョンにより `_core` の有無で分岐）、`np.ndarray`、`np.dtype` を `torch.serialization.add_safe_globals()` で許可リストに登録する。
- **引数**: なし
- **返り値**: なし
- **副作用**: モジュールグローバル `_SAFE_GLOBALS_REGISTERED` を `True` に更新し、torchのシリアライズ許可リストをグローバルに変更する。
- **冪等性**: 2回目以降の呼び出しは即 return（フラグで多重登録を防止）。
- **注意（実装コメントより）**: ここで許可しているのは「自身が書き出した.ptファイルの復元に必要な numpy 内部関数」のみであり、他者由来の信頼できないファイルの読み込みにこの安全性を流用してはならない。

#### `date_to_days_since_epoch(date_series: pd.Series) -> np.ndarray`
- **概要**: 日付列を `TIME_ENCODING_EPOCH`（2000-01-01）からの経過日数（float32）に変換する。
- **引数**: `date_series` — 日付相当の値を持つ `pd.Series`（`pd.to_datetime` でパース可能なもの）。
- **返り値**: `np.ndarray`（`float32`、shape `(N,)`）。
- **設計意図**: sin/cos変換はここでは行わない。Time2Vecは周波数が学習パラメータであるため、前処理側は「生の時間スカラー」を渡すだけにするのが正しい、という方針がdocstringに明記されている。

#### `build_category_vocab(values) -> Dict[str, int]`
- **概要**: カテゴリ列のユニーク値から `{値の文字列: 整数ID}` の辞書（vocab）を構築する。
- **引数**: `values` — イテラブル（列のユニーク値候補。関数内で `str()` 化・ソートされる）。
- **返り値**: `Dict[str, int]`。キーはソート済み文字列化ユニーク値、値は0始まりの連番。末尾に `"<UNK>"` を追加し、`len(vocab)-1` を割り当てる。
- **設計意図**: `"<UNK>"` を用意することで、vocab構築後に出現した未知カテゴリ（例: train期間に無かった業種区分がval/testで出現、あるいは原資産の無いオプションの `UndSSO=None`）にも安全に対応できる。

#### `encode_category(values, vocab: Dict[str, int]) -> np.ndarray`
- **概要**: カテゴリ列を `vocab` を用いて整数IDの配列に変換する。
- **引数**: `values` — カテゴリ値のイテラブル。`vocab` — `build_category_vocab` で構築した辞書。
- **返り値**: `np.ndarray`（`int64`）。`vocab` に存在しない値は `vocab["<UNK>"]` にマップされる（`vocab.get(str(v), unk)`）。

#### `vocab_path(vocab_dir: str, serial_id: int, node_type: str, column: str) -> str`
- **概要**: vocab JSONファイルの保存パスを組み立てる。
- **返り値**: `{vocab_dir}/vocab_{serial_id}_{node_type}_{column}.json`

#### `save_vocab(vocab: Dict[str, int], path: str) -> None`
- **概要**: vocab辞書をJSONとして保存する。`os.makedirs(..., exist_ok=True)` で親ディレクトリを自動作成する。`ensure_ascii=False, indent=2` で書き出す。

#### `load_vocab(path: str) -> Dict[str, int]`
- **概要**: 保存済みvocab JSONを読み込む。

#### `get_vocab_sizes(serial_id: int, node_type: str, vocab_dir: str = DEFAULT_VOCAB_DIR) -> Dict[str, int]`
- **概要**: モデル側で `nn.Embedding(num_embeddings=...)` を構築する際に使うため、`node_type` の各カテゴリ列（`CATEGORICAL_COLUMNS[node_type]`）についてvocabサイズ（`<UNK>` 込み）を返す。
- **返り値例**: `get_vocab_sizes(1, "stock") -> {"S33": 34, "S17": 18, ...}`、`get_vocab_sizes(1, "option") -> {"ProdCat": 5, "UndSSO": 241, "CM": ...}`。
- **前提条件**: 対象の `vocab_{serial_id}_{node_type}_{col}.json` が事前に `build_category_vocabs()`（`preprocess` クラス）等で生成済みであること。

#### `fetch_edge_index(serial_id: int) -> Tuple[pd.arrays.ArrowStringArray, pd.arrays.ArrowStringArray]`
- **概要**: `sql.fetch.edge_index(serial_id)` からエッジテーブルの `src_node_id` / `dst_node_id` 列を取得する。
- **返り値**: `(src, dst)` の2要素タプル。各要素は長さ `E`（全エッジ数）の文字列配列（例: `"stock_11_1301"`）。
- **注意（docstring）**: 戻り値はまだ整数インデックス化されていない文字列node_id。`torch.tensor` 化する前に必ず `build_node_id_to_idx()` → `map_edge_ids_to_idx()` を通す必要がある。
- **実装上の注意**: `assert isinstance(src, pd.arrays.ArrowStringArray)` という表明があるが、これは `fetch.edge_index` の実装（DuckDB→pandas変換）がArrow拡張型を返すことを前提にした表明的アサーションであり、pandasの設定によっては通常の `numpy.ndarray of dtype object` になり得る点に注意。

#### `fetch_edge_attr(serial_id: int, attr_name: str) -> np.ndarray`
- **概要**: エッジの指定属性列（例: `"edge_type"`, `"edge_weight"`, `"observable_time_id"`）をDBから取得し、1次元 `np.ndarray` として返す。
- **実装**: `fetch.edge_attr(...).values.transpose().flatten()`（単一列なので実質そのままflatten）。

#### `class NodeFeatsPayload(TypedDict)`
- **概要**: `graph_node.feats` 列に保存されているJSONの構造を表す型。`json.loads()` の戻り値は本来 `Any` であり型チェッカーが中身を追えないため、`parse_feats_json()` でこの型に `cast` し、以降の辞書アクセスに型を付けるためのもの。
- **フィールド**:
  - `cont: Dict[str, float]` — 連続値特徴量
  - `cat: Dict[str, int]` — カテゴリの整数ID
  - `date: Dict[str, float]` — 日付の経過日数

#### `parse_feats_json(raw: str) -> NodeFeatsPayload`
- **概要**: `feats` 列のJSON文字列をパースし、`NodeFeatsPayload` として扱えるように `cast` する。

#### `extract_cont(payload: NodeFeatsPayload) -> List[float]`
- **概要**: `payload["cont"]` の値を辞書の挿入順（＝生成時のDataFrame列順）でリスト化する。

#### `extract_cat(payload: NodeFeatsPayload, cat_cols: List[str]) -> List[int]`
- **概要**: `cat_cols` に指定した列順で `payload["cat"]` から値を取り出す。**列順は呼び出し側で明示的に固定**される（辞書順に依存しない）。

#### `extract_date(payload: NodeFeatsPayload, date_cols: List[str]) -> List[float]`
- **概要**: `extract_cat` と同様に、`date_cols` の順で `payload["date"]` から値を取り出す。

#### `fetch_node_table(serial_id: int, node_type: str) -> Dict[str, np.ndarray]`
- **概要**: 指定 `node_type`（`stock`/`statement`/`option`/`future` いずれも可。node_type非依存の汎用実装）の全ノードをDBから取得し、モデル入力に必要な各種配列に整形する。
- **処理内容**:
  1. `fetch.node_table(serial_id, node_type)` でDataFrameを取得（`node` と `feats` をJOINしたもの）。
  2. `node_id` 文字列で `sort_values` し、`reset_index(drop=True)` する。**この並び順がそのままローカル整数インデックス（0,1,2,...）として扱われる**。
  3. `feats` 列（JSON文字列）を `parse_feats_json` でパースし、`extract_cont` / `extract_cat` / `extract_date` でそれぞれ `np.stack` して2次元配列化。
- **返り値**: 以下のキーを持つ辞書。
  - `x`: `(N, num_cont)` float32 — 連続値特徴量
  - `cat_x`: `(N, num_cat)` int64 — カテゴリの整数ID（列順は `CATEGORICAL_COLUMNS[node_type]`）
  - `date_x`: `(N, num_date)` float32 — 日付の経過日数（列順は `DATE_COLUMNS[node_type]`）
  - `is_target`: `(N,)` bool
  - `time_id`: `(N,)` int64
  - `node_str_id`: `(N,)` str — ソート済みnode_id文字列
- **前提条件（★docstringで要確認と明記）**: 「エッジ側で使われている整数インデックスの順序」と「特徴量テーブルの行の順序」が一致している前提はここでは取らない設計になっており、代わりに node_id文字列でソートした順序を正としてエッジ側もこの順序にマッピングし直す（`build_node_id_to_idx` / `map_edge_ids_to_idx` 経由）。DBスキーマは `graph_node` に `node_id`, `is_target`, `time_id`, `feats` 列がある想定（実装コメント参照）。

#### `build_node_id_to_idx(node_str_id: np.ndarray) -> Dict[str, int]`
- **概要**: `node_str_id` 配列（`fetch_node_table` が返すもの）から `{node_id文字列: ローカル整数インデックス}` の辞書を作る。単純な `enumerate` によるマッピング。
- **前提条件**: 入力の並び順がそのままローカルインデックスであるという契約（`fetch_node_table` 側で保証）。

#### `map_edge_ids_to_idx(src_ids, dst_ids, src_map, dst_map) -> np.ndarray`
- **概要**: 文字列の `src_ids` / `dst_ids`（`pd.arrays.ArrowStringArray`）を、それぞれ対応するノードタイプの整数インデックスに変換する。
- **引数**:
  - `src_ids`, `dst_ids`: 文字列node_id配列
  - `src_map`, `dst_map`: `build_node_id_to_idx` で構築した `{node_id: idx}` 辞書
- **返り値**: `(2, E)` の `np.int64` 配列（`[src_idx行; dst_idx行]`）。
- **例外**: `src_map` / `dst_map` に存在しない node_id が来た場合、`KeyError` を再送出（メッセージに「ノード生成とエッジ生成の対象範囲がズレている可能性」を付記）。**サイレントに握りつぶさず早期検出する設計**（実装コメントで明言）。実際にこの検出に助けられて発見・修正したバグの例として、`derivative_corr.build_peer_corr_edges()` の当初実装が「直近の窓内にデータがあった契約」を「今週も存在する契約」と取り違え、存在しない `future_202307_168020019` 等を指すダングリングエッジを生成していたケースがある（現在は修正済み。[3. derivative_corr.py](#3-derivative_corrpy)参照）。

### `class preprocess`

生の `financials_df` / `prices_df` / `options_df` / `futures_df` を受け取り、
`node` / `edge` / `feats` テーブルへ変換・格納するクラス。

#### `__init__(self, financials_df, prices_df, options_df, futures_df, serial_id: int = 1, vocab_dir: str = DEFAULT_VOCAB_DIR)`
- **概要**: 4つのDataFrameをインスタンス変数に保存するとともに、それぞれの `week_id` ユニーク値の和集合を `self.unique_week_id`（ソート済みリスト）として保持する。

#### `get_unique_week_id`（`@property`）
- **概要**: `self.unique_week_id` を返す読み取り専用プロパティ。

##### 1. graph_edge に関する処理

#### `stock_corr_stock_preprocess(self) -> None`
- **概要**: 銘柄間のCAPM残差相関エッジ、および同一銘柄の週次連続エッジを構築し、`insert.edge` でDBに格納する。
- **処理内容**:
  1. `capm_corr.build_firm_corr_edges(prices_df)` で週ごとの `(edge_index, edge_weight)` と `firm_id_order` を取得。
  2. `prices_df` から実在する `(week_id, Code)` の組を `valid_pairs`（set）として構築。
  3. 各週について、`edge_index` の整数インデックスを `firm_id_order` で銘柄コードに変換し、`(week_id, code)` が `valid_pairs` に存在するペアのみ残す（存在しないノードへのダングリングエッジを防止）。
  4. 残ったペアを `edge_type = "stock__corr__stock"` として `insert.edge` でDB登録。`edge_id` は `f"stock__corr__stock_{week}_{src}_{dst}"`。
  5. さらに、同一銘柄について前週→当週の連続エッジ（`edge_weight=1.0`）を全銘柄分追加登録する（同じ `stock__corr__stock` relationにまとめる設計）。
- **既知のデータ不整合対応（docstring記載）**: `capm_corr.build_firm_corr_edges()` は固定の銘柄ユニバースを前提に相関を計算するため、上場前の週にもエッジを生成しうる（例: 2024年新規上場銘柄が2015年時点のエッジに現れる）。`node_id_define()` は実在する `(week, code)` からしかノードを作らないため、フィルタで整合させている。
- **副作用**: `print` で件数ログ（採用件数/スキップ件数）を出力。DBへの `insert.edge` 呼び出し（週ごと・銘柄ごとに複数回）。
- **既知の副作用（実測値）**: `capm_corr.py` の `CAPM_RESIDUAL_STORED_PATH`（キャッシュパス）が
  誤って `graph_v2` を指していた時期のバグの影響で、既存の全期間キャッシュが常にヒットせず
  CAPM残差が毎回不完全な範囲で再計算されていた。パス修正後は既存キャッシュが正しく
  参照されるようになり、同一条件（20週スライスでの検証）でのエッジ数が
  79,458件→178,576件に増加している（修正前の値が過小だった）。

#### `_insert_peer_corr_edges(self, peer_corr: derivative_corr.PeerCorrEdges, node_type: str) -> None`
- **概要**: `derivative_corr.build_peer_corr_edges()` の結果（`week_id -> [(src_code, dst_code, weight), ...]`）を `{node_type}__corr__{node_type}` エッジとしてDB登録する共通処理。`option_corr_option_preprocess` / `future_corr_future_preprocess` から呼ばれる。
- **処理内容**: 週ごとに `edge_id` / `src_node_id` / `dst_node_id` / `edge_weight_list` / `observable_time_id` を組み立て、`insert.edge` を1回呼ぶ（週単位でのバルクinsert）。

#### `option_corr_option_preprocess(self) -> None`
- **概要**: 同一原資産（`UndSSO`）を持つオプション契約同士の相関エッジ（`option__corr__option`）を作成する。
- **処理内容**: `derivative_corr.build_peer_corr_edges(options_df, group_col="UndSSO", code_col="Code", close_col="AdjC")` を呼び、結果を `_insert_peer_corr_edges` でDB登録する。
- **対象外**: `UndSSO` がNULL（原資産の無い指数・債券オプション、`NK225E`/`TOPIXE`/`JGBLFE`）はグループ化できないため対象外。

#### `future_corr_future_preprocess(self) -> None`
- **概要**: 同一商品区分（`ProdCat`）を持つ先物契約同士の相関エッジ（`future__corr__future`）を作成する。
- **処理内容**: `derivative_corr.build_peer_corr_edges(futures_df, group_col="ProdCat", code_col="Code", close_col="AdjC")` を呼び、結果を `_insert_peer_corr_edges` でDB登録する。

#### `_prev_chain_preprocess(self, df: pd.DataFrame, node_type: str) -> None`
- **概要**: 同一契約（`Code`）の時系列エッジ（前週 -> 今週）を作成する共通処理。`option_prev_option_preprocess` / `future_prev_future_preprocess` から呼ばれる。`statement_prev_statement_preprocess` と意味合いは同じだが実装方式が異なる（下記参照）。
- **処理内容**: `df.groupby("Code")["week_id"].shift(1)` で各契約の「前週の week_id」を一括算出し、`dropna` して有効な行だけを対象に、1回のバルク `insert.edge` でエッジを登録する（完全にベクトル化されている）。
- **設計上の経緯（★重要）**: 当初は `statement_prev_statement_preprocess` と同じ「契約コードごとにPythonループを回し、都度 `insert.edge()`（＝DuckDB接続を1回張り直す）」という実装だったが、これは銘柄（約4,000コード）や決算（約3,000コード）では許容範囲でも、**限られた週範囲（20週）に絞ってすら約3万契約に達するオプションでは実測約30分かかり、全期間（約27万契約）では実用不可能**と判明した。そのため `groupby + shift` によるベクトル化 + 単一バルクinsertに書き換えており、同条件で数秒に短縮されている。

#### `option_prev_option_preprocess(self) -> None`
- **概要**: `self._prev_chain_preprocess(self.options_df, node_type="option")` を呼ぶだけ。

#### `future_prev_future_preprocess(self) -> None`
- **概要**: `self._prev_chain_preprocess(self.futures_df, node_type="future")` を呼ぶだけ。

#### `stock_derivative_option_preprocess(self) -> None`
- **概要**: 銘柄ノード → その原資産とするオプション契約ノードへの `stock__derivative__option` エッジを作成する。
- **処理内容**:
  1. `options_df` から `UndSSO` がNULL（原資産の無い指数・債券オプション）の行を除外。
  2. `prices_df` から実在する `(week_id, Code)` の組を `valid_pairs` とし、`options_df` の `(week_id, UndSSO)` と inner join（statement__report__stockと同じ「実在するノードにのみエッジを張る」パターン）。
  3. `src = stock_{week}_{UndSSO}`, `dst = option_{week}_{Code}` のエッジを構築し `insert.edge` で一括登録。
- **前提**: `UndSSO` は取得元SQL（`get_table_to_option.sql`）側で既に `eqt_main.Code` と同じ5桁表記（4桁の原資産コードに `'0'` を付与）に正規化済みであること。

#### `stock_derivative_future_preprocess(self) -> None`
- **概要**: 全 `is_target` 銘柄ノード → 主要な株価指数先物（期近物）ノードへの `stock__derivative__future` エッジ（"market backbone"構造）を作成する。
- **処理内容**:
  1. `futures_df` を `MARKET_INDEX_FUTURE_PRODCATS`（既定 `["NK225F","TOPIXF"]`）でフィルタ。該当が無ければ警告を出して早期return。
  2. `SQRemainingDays >= 0` を優先しつつ最小値の契約（＝期近物）を `(week_id, ProdCat)` ごとに1本選ぶ（全て期限切れ扱いの場合は最大値＝最も期限切れが浅いものを採用）。
  3. `prices_df` から `Mkt in {"0000","0500"}` の銘柄を対象銘柄として抽出し、`week_id` をキーに期近物と直積（＝その週の全対象銘柄 × 選定された先物本数、通常2本）で結合。
  4. `src = stock_{week}_{stock_code}`, `dst = future_{week}_{future_code}` のエッジを構築し `insert.edge` で一括登録。
- **設計意図**: 先物は個別株の原資産を持たない（指数・債券・通貨先物のみ）ため、個別株と1対1で紐付けるルールが存在しない。そのため「市場全体のシステマティックリスクを媒介するハブ」として、主要指数先物の期近物に全対象銘柄を一律接続する設計を採用している（ユーザー確認済みの方針）。
- **既知の設計上の留意点**: この設計により `future` 側から見た `rev_derivative`（future→stock）の次数はその週の対象銘柄数と同程度（数百〜数千）になり得るハブ構造になる。`get_loaders()` の近傍サンプリング数（既定 `NUM_NEIGHBORS_PER_HOP=10`）はこの次数に対してごく一部しかサンプリングしないため、意図通り「市場情報の集約」として機能するか、無関係な銘柄のノイズを混入させるかは学習結果を見て評価する必要がある。

#### `statement_prev_statement_preprocess(self) -> None`
- **概要**: 各銘柄の決算ノードについて、時系列順に「前期→今期」の `statement__prev__statement` エッジを構築し、`insert.edge` で格納する。
- **処理内容**: `financials_df["Code"]` のユニークコードごとにPythonループし、`week_id` を `shift(1)` して前期・今期のnode_idペアを作る（`edge_weight=1.0` 固定）。コードごとに `insert.edge` を呼ぶ（決算は約3,000コード程度のため許容範囲。オプション/先物向けにはこの実装は使わず `_prev_chain_preprocess` のベクトル化版を使う。上記参照）。
- **副作用**: `\r` で進捗（`Processing code: {code} ({i}/{len(codes)})`）を上書き表示。

#### `statement_report_stock_preprocess(self) -> None`
- **概要**: 決算ノード→対応銘柄週次ノードへの `statement__report__stock` エッジを構築する（旧名 `stock_report_statement_preprocess` から、方向と名前の矛盾を解消するため改名）。
- **処理内容**:
  1. `financials_df` と `prices_df` の `(week_id, Code)` を `inner join`し、実在する組み合わせのみ抽出（`valid_pairs`）。
  2. `src = statement_{week}_{code}`, `dst = stock_{week}_{code}` のエッジを構築し `insert.edge` で登録。
  3. `merged` が空なら早期return。
- **既知のデータ不整合対応（docstring記載）**: 2013/07/16の東証・大証統合、名証→東証の上場替え等により、決算発表履歴はあるが対応する株価データが無い組が1214銘柄で発生する（大証専売銘柄・上場替え銘柄など）。固定日付での一律区切りでは上場替え時期が銘柄ごとに異なる122銘柄（例: 5356, 5461）に対応できないため、「株価データが実在する `(week,code)` にのみエッジを張る」という汎用的な存在チェックに一般化している。決算データ自体は削除せず、report エッジが無い期間の statement ノードは `statement__prev__statement` チェーンを通じて多ホップで参照可能なまま残す設計。
- **副作用**: `print` でスキップ件数のログを出力。

##### 2. graph_node に関する処理

#### `node_id_define(self) -> None`
- **概要**: `financials_df`（→`statement`）・`prices_df`（→`stock`）・`options_df`（→`option`）・`futures_df`（→`future`）の4DataFrameから `node_id` / `is_target` / `ticker` / `node_type` / `time_id` を定義し、`insert.node` でDB登録する。node_type非依存の汎用実装であり、対象DataFrameを増やしたい場合は `using_df_list` にタプルを追加するだけでよい。
- **処理内容**:
  - `node_id = f'{node_type}_{week_id}_{Code}'`
  - `stock` ノードの `is_target` は `Mkt in {"0000", "0500"}` の場合に `True`（それ以外の市場区分の銘柄は予測対象外）。
  - `statement`/`option`/`future` ノードの `is_target` は常に `False`。
- **副作用**: `print` で進捗ログ。DB登録。

##### 3. カテゴリ変数のvocab構築

#### `build_category_vocabs(self) -> None`
- **概要**: `CATEGORICAL_COLUMNS` に定義された各 `(node_type, column)`（`stock`/`statement`/`option`/`future` の4タイプ分）について、全期間データから `build_category_vocab` でvocabを構築し、`save_vocab` でディスクに保存する。
- **設計意図（docstring）**: train/val/testを分けず全期間で構築する。これは「未来のラベルを覗き見る」リークではなく、「業種区分・市場区分としてどんな値が存在し得るか」というカテゴリ全体の定義に過ぎないため区別される、という方針が明記されている（将来の新規カテゴリに備えた `<UNK>` 枠も用意）。`option.UndSSO` のようにNULL値を含み得る列も、`str(None)`＝`"None"` として1つのカテゴリ扱いになる。
- **副作用**: `print` でカテゴリ数ログ。ファイル書き込み（`save_vocab`）。

##### 4. node_feats に関する処理

#### `node_feats_define(self) -> None`
- **概要**: `stock`/`statement`/`option`/`future` 各ノードの特徴量を `{"cont": {...}, "cat": {...}, "date": {...}}` 形式のJSONとして `feats` テーブルに格納する。node_type非依存の汎用実装。
- **処理内容**:
  1. `week_id`, `Code` 列の存在チェック（無ければ `ValueError`）。
  2. `cont_cols` = 全列から `week_id`, `Code`, カテゴリ列, 日付列を除いた残り（`option`/`future`では `AdjO/H/L/C/Vo/Va/OI` や `DeviationRate`/`SQRemainingDays`/`Moneyness`/`IV`/`NULL_TYPE_*` 等がここに入る）。
  3. カテゴリ列は事前に保存済みvocab（`build_category_vocabs()` が先に実行されている前提）を読み込み `encode_category` で整数化。日付列は `date_to_days_since_epoch` で経過日数化。
  4. 1000行単位のバッチでループし、各行について `payload = {"cont": {...}, "cat": {...}, "date": {...}}` を `json.dumps` し、`insert.feats` でDB登録。
- **返り値**: なし
- **副作用**: `print` で進捗（バッチ範囲）を `\r` 上書き表示。DB登録（バッチごとに `insert.feats` 呼び出し）。
- **前提条件**: `build_category_vocabs()` が本メソッドより先に実行済みであること（`insert_to_graph_info_table()` の呼び出し順で保証）。

##### 5. まとめて実行

#### `insert_to_graph_info_table(self) -> None`
- **概要**: 上記の12メソッドを決められた順序で一括実行するオーケストレーションメソッド。
- **実行順序**:
  1. `statement_prev_statement_preprocess`
  2. `statement_report_stock_preprocess`
  3. `stock_corr_stock_preprocess`
  4. `option_corr_option_preprocess`
  5. `option_prev_option_preprocess`
  6. `future_corr_future_preprocess`
  7. `future_prev_future_preprocess`
  8. `stock_derivative_option_preprocess`
  9. `stock_derivative_future_preprocess`
  10. `node_id_define`
  11. `build_category_vocabs`（**`node_feats_define` より前に実行し、vocabを確定させる必要があるため明示的にこの順序**）
  12. `node_feats_define`
- **順序に関する注記**: エッジ系の1〜9はいずれも `insert.edge` が単に文字列node_idを書き込むだけで外部キー制約が無いため、ノード（10）より先に実行しても問題ない（DuckDB側にFK制約は無い）。
- **副作用**: 各ステップの実行時間を `print("preprocess time", dt.now() - now)` で出力。

### `class graphDataSet(InMemoryDataset)`

全期間・全銘柄・全ノードタイプ（4種類）を含む「単一の」`HeteroData` を保持する PyG `InMemoryDataset`。train/val/testの分割はここでは行わない（`get_loaders` 側でマスクとして行う）。

#### `__init__(self, root, transform=None, pre_transform=None, serial_id: int = 1, vocab_dir: str = DEFAULT_VOCAB_DIR)`
- **概要**: `serial_id`, `vocab_dir` を保存し、`_allow_numpy_globals_for_torch_load()` を呼んでから親クラス `InMemoryDataset.__init__` を実行、`self.load(self.processed_paths[0])` でロードする。
- **注意**: 親クラスの `__init__` 内部で `process()` が（`processed_file_names` が存在しない場合に）自動的に呼ばれるのがPyGの標準動作。

#### `raw_file_names`（`@property`）
- **返り値**: `[]`（rawファイル自体は使わず、DB経由で完結するため）。

#### `processed_file_names`（`@property`）
- **返り値**: `[f"data_{self.serial_id}_full.pt"]`。単一グラフのみを保持するためファイルは1つ。

#### `num_classes`（`@property`）
- **返り値**: `2`（固定値。二値分類タスクを想定）。

#### `download(self) -> None`
- **概要**: 何もしない（PyGの `InMemoryDataset` 契約上必要なオーバーライド）。

#### `_ensure_db_built(self) -> None`
- **概要**: raw データのDB登録（前処理）が未実行なら実行する。
- **処理内容**: `graph_info_{serial_id}.duckdb` の存在チェック。存在すれば即return。無ければ `create.graph_info(serial_id)` でテーブル作成後、`fetch.financials()` / `fetch.prices()` / `fetch.options()` / `fetch.futures()` の4つを取得して `preprocess` を構築し、`insert_to_graph_info_table()` を実行。
- **べき等性**: DBファイルの存在有無で判定するため、既存DBがあれば再実行されない（差分更新は非対応）。

#### `_node_str_id_path(self, node_type: str) -> str`
- **概要**: `node_str_id` を保存する `.npy` ファイルのパスを組み立てる: `{processed_dir}/node_str_id_{serial_id}_{node_type}.npy`。
- **設計意図（docstring）**: `HeteroData` の中には入れず別ファイルにする理由は、`NeighborLoader` が全ノード属性を自動でテンソル化しようとするため、文字列配列を `data[node_type]` に直接持たせると `TypeError: can't convert np.ndarray of type numpy.str_` になるため。

#### `load_node_str_id(self, node_type: str) -> np.ndarray`
- **概要**: 指定 `node_type` の `node_str_id` 配列（`.npy`）をロードする。`allow_pickle=False`。
- **使い方（docstringのコメント例）**:
  ```python
  global_idx = batch['stock'].n_id.numpy()  # NeighborLoaderが自動付与
  str_ids = dataset.load_node_str_id('stock')[global_idx]
  ```
  学習ループ内でバッチに含まれるノードの実体（文字列ID）を特定する用途。`'stock'` を `'option'`/`'future'`/`'statement'` に置き換えても同様に使える。

#### `_build_full_graph(self) -> HeteroData`
- **概要**: DBから全ノード・全エッジを取得し、単一の `HeteroData` を構築する中核メソッド。
- **処理内容**:
  1. **ノード側**: `["stock", "statement", "option", "future"]` の各 `node_type` について `fetch_node_table` を呼び、`data[node_type].x / cat_x / date_x / is_target / time_id` を設定。同時に `node_str_id` を `.npy` として保存し、`build_node_id_to_idx` で `node_id_to_idx[node_type]` 辞書を構築（エッジ側の整数化に使用）。
  2. **エッジ側**: `fetch_edge_index` / `fetch_edge_attr("edge_type")` / `fetch_edge_attr("edge_weight")` / `fetch_edge_attr("observable_time_id")` を取得。`edge_type` のユニーク値（`edge_type_names`）ごとにループし、`"__"` で `(src_t, rel, dst_t)` に分解、該当行だけを `map_edge_ids_to_idx` で整数インデックス化して `data[src_t, rel, dst_t].edge_index / edge_weight / edge_time` に格納。**この部分は完全に node_type/edge_type非依存の汎用実装であり、DB上の `edge_type` 文字列がそのまま `HeteroData` のエッジ種別になる**（＝新しいエッジ種別を追加する際、本メソッド自体の変更は不要）。
  3. `REVERSE_RELATIONS` に該当する `(src_t, rel, dst_t)` については、`edge_index_int` の行を `[1, 0]` で入れ替えた逆エッジを `data[dst_t, rev_rel, src_t]` として追加登録（`edge_weight` / `edge_time` は元エッジと同じ値を再利用）。
- **返り値**: 構築済みの `HeteroData`。
- **副作用**: `processed_dir` へのディレクトリ作成、`node_str_id_*.npy` の書き込み（4ノードタイプ分）。

#### `process(self) -> None`
- **概要**: PyG `InMemoryDataset` の標準フック。`_ensure_db_built()` → `_build_full_graph()` → `self.save([data], self.processed_paths[0])` を順に実行する。

### 関数: `get_loaders(...)`

```python
def get_loaders(
    serial_id: int = 1,
    split_1_per: float = graph_params.SPLIT_1_PER,   # 既定 0.7
    split_2_per: float = graph_params.SPLIT_2_PER,   # 既定 0.85
    batch_size: int = graph_params.BATCH_SIZE,       # 既定 32
    num_neighbors: Dict[Tuple[str, str, str], List[int]] | None = None,
)
```
- **概要**: 単一グラフから train/val/test 用の3つの `NeighborLoader` を構築する。
- **処理内容**:
  1. `graphDataSet(root="scripts/datap/graph/DS", serial_id=serial_id)` を構築し、`data = dataset[0]` を取得。
  2. `data["stock"].time_id` の最小値・最大値から `split_1 = t_min + split_1_per*(t_max-t_min)`、`split_2 = t_min + split_2_per*(t_max-t_min)` を計算（**時間で線形按分したしきい値**。週IDの分布が一様でない場合、実際のサンプル数比とは一致しない点に注意）。
  3. `is_target` かつ `time_id` の範囲で `train_mask` / `val_mask` / `test_mask`（`stock` ノードのみ）を作成。
  4. `num_neighbors` が未指定の場合、**グラフに実在する全エッジ種別（`data.edge_types`）に対して動的に**辞書を構築する:
     ```python
     per_hop = [graph_params.NUM_NEIGHBORS_PER_HOP] * graph_params.NUM_HOPS  # 既定 [10, 10]
     num_neighbors = {edge_type: per_hop for edge_type in data.edge_types}
     ```
     （旧版はエッジ種別を1件ずつハードコードした辞書だったが、種別追加時の書き忘れを防ぐため動的生成に変更した。関係ごとに個別の値を与えたい場合は、この引数に辞書を渡して明示的に上書きする。）
  5. 内部関数 `_make_loader(mask, shuffle)` で `NeighborLoader(data, num_neighbors=..., input_nodes=("stock", mask), batch_size=batch_size, shuffle=shuffle)` を構築。train のみ `shuffle=True`。
- **返り値**: `(train_loader, val_loader, test_loader)` の3-tuple（いずれも `NeighborLoader`）。
- **設計意図**: グラフ自体は分割しない（過去情報へのアクセスを維持するため）。`is_target` かつ該当期間の `stock` ノードのみを `input_nodes`（＝バッチ生成の起点かつ損失計算対象）とすることで、`statement`/`option`/`future` ノードや非対象銘柄がバッチの起点にならないようにしている。

### 関数: `mock_code(serial_id: int = 1)`
- **概要**: `get_loaders` の疎通確認用モックコード。3つのローダーそれぞれを全件イテレートし、`batch` を `print` するだけ。
- **用途**: パイプライン全体（DB構築〜HeteroData構築〜NeighborLoader）が例外なく動作するかの動作確認。`for batch in loader: print(batch)` を3ローダー分繰り返すため、実行するとバッチ数だけ同じ形式の `HeteroData(...)` ブロックが連続して表示される（これはバグではなく仕様）。

---

## 2. capm_corr.py

graph_v1 の以下のロジックを単一モジュールに集約・移植したもの（モジュールdocstring記載）:

- `graph_v1/edge_matrix/constructor/spacial_c.py` の `_utils_firm2firm`（`_rolling_capm_residual` / `_add_capm_factors_column` / `_iter_prices_adjacent_matrix`）
- 同ファイルの `Spacial.register_firm2firm_edge`
- `graph_v1/edge_matrix/constructor/utils.py` の `u_common`（週次進捗表示）

**graph_v1との違い**:
- 出力がPyG形式（週IDごとに `edge_index (2,E)` と `edge_weight (E,)`。`('firm','corr','firm')` のHeteroDataにそのまま投入可能）。
- SQL取得層に依存せず、価格DataFrameまたは残差行列を引数で受け取る。
- CAPM残差行列はparquetキャッシュ、相関計算は週次進捗表示する点はgraph_v1と同じ。

想定する価格DataFrameの列: `week_id, Code, r_i(個別リターン), r_m(市場リターン), r_f(無リスク金利), ...`（`sql/get_table_to_CAPM.sql` の出力に対応）。

> **旧 `capm_corr_constants` クラスは削除済み**。ハイパーパラメータは全て
> `scripts/datap/graph/cons.py` の `graph_params`（`CAPM_*` 系）に一元化されている
> （詳細は[4. cons.py](#4-conspy)参照）。本ファイルの各関数は、そのデフォルト値を
> 関数シグネチャのデフォルト引数として参照するのみで、値自体の定義は持たない。

### `class _color`
進捗表示用のANSIエスケープコード定数（graph_v1の `print_constants` 相当）。`CLEAR`, `MAGENTA`, `CYAN`, `RESET` の4定数。モジュールプライベート。

### `class FirmCorrEdges(NamedTuple)`
CAPM残差相関エッジの構築結果を表す。
- `firm_id_order: pd.Index` — エッジ行列の行/列に対応する銘柄コードの並び（残差計算後に確定。全NaNの銘柄は除外されるため計算前とは異なりうる）。
- `edges: Dict[int, Tuple[torch.Tensor, torch.Tensor]]` — `week_id -> (edge_index (2,E) long, edge_weight (E,) float32)`。相関行列は対称なので `(i,j)` と `(j,i)` の両方向が含まれる。

### `_display_iter(task_summary, week_id=None, processing_ratio=None, sparse_edge_matrix=None) -> None`
- **概要**: `\r` で行を上書きしながら週次の進捗を表示する（graph_v1の `u_common` の移植）。
- **引数**: `task_summary`（タスク名）、`week_id`（省略可）、`processing_ratio`（0〜1、省略可）、`sparse_edge_matrix`（疎エッジ行列、shapeとnnzを表示、省略可）。
- **改行判定**: `processing_ratio is not None and processing_ratio >= 1.0` のとき改行、それ以外は行末スペースのみ（次回の `\r` で上書きする前提）。

### `_display_note(note_title: str, content: object) -> None`
- **概要**: `" - Title: [note_title]: content"` の形式で1行 `print` する（進捗の合間の注記表示用）。

### `_rolling_capm_residual(stock_ret: pd.Series, market_ret: pd.Series, window: int = 52) -> Tuple[pd.Series, pd.Series]`
- **概要**: CAPMを週次ローリング推定し、残差リターンとベータ系列を返す（graph_v1の移植）。
- **引数**: `stock_ret` — 個別株の超過リターン系列（`r_i - r_f`）。`market_ret` — 市場の超過リターン系列（`r_m - r_f`）。`window` — ローリングウィンドウのサイズ（週）。
- **処理内容**: `statsmodels.regression.rolling.RollingOLS(endog=r_i, exog=[const, r_m], window=window).fit()` でローリング回帰し、`fitted = const + r_m係数 * r_m`、`residual = r_i - fitted` を計算。
- **返り値**: `(residual, beta系列)` の2-tuple（いずれも `pd.Series`）。
- **注意**: `RollingOLS` は窓長に満たない場合にエラーを出すため、呼び出し側（`residual_matrix_from_prices`）で事前に `len(filtered) < window_size_for_capm` のチェックを行い、満たない銘柄はスキップしている。

### `residual_matrix_from_prices(prices_df, *, window_size_for_capm=graph_params.CAPM_WINDOW_SIZE_FOR_CAPM, residual_stored_path=graph_params.CAPM_RESIDUAL_STORED_PATH, use_cache=True) -> pd.DataFrame`
- **概要**: 全銘柄のCAPM残差リターンを計算し、`week_id x Code` 行列にピボットする。
- **処理内容**:
  1. `use_cache=True` かつキャッシュ（parquet、既定 `scripts/datap/graph/store/returns_residual_matrix.parquet`）が存在すればロードのみ行い即return。
  2. `prices_df` を `dropna()` してコピーし、`residual` / `beta` 列を `NaN` で初期化。
  3. `Code` ごとにループし、`len(filtered) < window_size_for_capm` の銘柄は `unmatched_codes` に記録してスキップ。それ以外は `_rolling_capm_residual` で残差・ベータを計算し元DataFrameに書き戻す。
  4. `residual` または `beta` が `NaN` の行を除外。
  5. `pivot(index="week_id", columns="Code", values="residual")` で行列化。
  6. `use_cache=True` なら `to_parquet(cache_path, engine="pyarrow")` で保存（親ディレクトリは自動作成）。
- **返り値**: `week_id` をindex、`Code` をcolumnsとする残差リターンの `pd.DataFrame`。
- **副作用**: `_display_iter` / `_display_note` によるログ出力（除外率・有効銘柄数の表示含む）。キャッシュファイルの読み書き。
- **★過去の不具合と修正**: `residual_stored_path` の既定値がリネーム前の `graph_v2` を指したままになっていたため、実在するキャッシュファイル（`scripts/datap/graph/store/returns_residual_matrix.parquet`）が常に見つからず、`use_cache=True` を指定しても実質的に毎回このメソッド内で残差を再計算していた（かつ渡された `prices_df` の範囲でしか計算しないため、`prices_df` が短期間に絞られている場合は52週窓を満たせず不完全な残差になっていた）。既定値を `graph_params.CAPM_RESIDUAL_STORED_PATH` 経由で `scripts/datap/graph/store/...` に修正済み。

### `_iter_rolling_corr_sparse(residual_matrix, window_size_for_corr, residuals_threshold, device) -> Iterator[Tuple[float, int, torch.Tensor]]`
- **概要**: 残差行列に対し、和・グラム行列を**差分更新（スライディングウィンドウ）**しながら週次のローリング相関を計算する（graph_v1の `_iter_prices_adjacent_matrix` の移植）。
- **アルゴリズム**:
  1. `residual_matrix.values` を `device` 上のtensor化。
  2. 最初の `window_size_for_corr` 週分の和 `s1` とグラム行列 `G = buf.T @ buf` を初期計算。
  3. `t = window_size_for_corr` から `T-1` までループし、各時点で `mean = s1/window`, `cov = G/window - outer(mean,mean)`, `std = sqrt(diag(cov))`, `corr = cov / outer(std,std)` を計算（共分散行列からの相関行列への標準変換）。
  4. `nan_to_num(nan=0.0)` でNaNを0埋めし、対角を0にし、`|corr| > threshold` でマスクした疎行列を `(進捗率, week_id, 疎相関行列)` として `yield`。
  5. スライド処理: 新しい週 `x_new` を加え古い週 `x_old` を引くことで `s1` と `G` をO(N²)の差分更新のみで次の時点に進める（毎回フルのグラム行列再計算をしない、計算量削減のための設計）。
- **返り値**: ジェネレータ。各要素は `(進捗率 (t+1)/T, week_id, coalesce前の疎相関tensor * mask)`。

### `_sparse_corr_to_edge_index(sparse_corr: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]`
- **概要**: 疎な相関行列をPyGの `edge_index` / `edge_weight` に変換する。
- **処理内容**: `sparse_corr.coalesce()` してから `indices()` を `long` に、`values()` を `float32` に変換し、いずれも `.cpu()` に移す。

### `iter_firm_corr_edges(*, prices_df=None, residual_matrix=None, window_size_for_capm=graph_params.CAPM_WINDOW_SIZE_FOR_CAPM, window_size_for_corr=graph_params.CAPM_WINDOW_SIZE_FOR_CORR, threshold=graph_params.CAPM_THRESHOLD, first_week_id=graph_params.CAPM_FIRST_WEEK_ID, residual_stored_path=graph_params.CAPM_RESIDUAL_STORED_PATH, use_cache=True, device=None, verbose=True) -> Iterator[Tuple[int, torch.Tensor, torch.Tensor, pd.Index]]`
- **概要**: 週IDごとにCAPM残差相関エッジを `yield` するジェネレータ（公開API）。
- **引数**: `prices_df` か `residual_matrix` のいずれかを渡す。両方渡した場合は `residual_matrix` を優先する。他のパラメータは `graph_params` のデフォルト値を継承。
- **処理内容**:
  1. `residual_matrix` が未指定なら `residual_matrix_from_prices` で計算。両方未指定なら `ValueError`。
  2. `firm_id_order = residual_matrix.columns`（残差計算で全NaN銘柄が落ちるため、並びはここで確定する。**毎回同じオブジェクトを返す**）。
  3. `device` 未指定時は `graph_params.CAPM_DEVICE`（既定 `None`）→ `None` ならさらに `"cuda" if torch.cuda.is_available() else "cpu"` の順で解決する（旧版は `capm_corr_constants.DEVICE` にimport時点で確定した文字列を持っていたが、現行版は呼び出し時に評価するよう変更されている）。
  4. `_iter_rolling_corr_sparse` の各要素について `week_id < first_week_id` の週はスキップ。それ以外は `_sparse_corr_to_edge_index` で変換し、`verbose=True` なら `_display_iter` でログ出力、`(week_id, edge_index, edge_weight, firm_id_order)` を `yield`。
- **返り値**: ジェネレータ。

### `build_firm_corr_edges(prices_df=None, *, residual_matrix=None, ..., verbose=True) -> FirmCorrEdges`
- **概要**: `iter_firm_corr_edges` の全週分をまとめて辞書に収集し、`FirmCorrEdges`（NamedTuple）として返す（公開API・非ジェネレータ版）。
- **引数**: `iter_firm_corr_edges` と同一のシグネチャ。
- **処理内容**: ジェネレータを全消費して `edges[week_id] = (edge_index, edge_weight)` を構築し、最後の `firm_id_order` を保持。1週も無かった場合（例: 全期間が `first_week_id` 未満等）は `firm_id_order = pd.Index([])` にフォールバック。
- **返り値**: `FirmCorrEdges(firm_id_order=..., edges=...)`。
- **呼び出し元**: `data_pipeline.preprocess.stock_corr_stock_preprocess` から呼ばれる。

---

## 3. derivative_corr.py

**新規ファイル**。`Option__corr__Option` / `Future__corr__Future` エッジ（同一グループ内の
オプション/先物契約同士の相関）を構築する。`capm_corr.py` とは目的が似ているが、
以下の理由から独立したモジュール・別アルゴリズムとして実装されている（モジュールdocstring記載）:

- デリバティブ契約は満期のある短命なインスタンス（オプションは全期間で約27万契約）であり、
  かつ「何と比較すべきか」が銘柄のように単一の市場ポートフォリオでは定義できないため、
  CAPM残差ではなく「同じグループ（原資産 `UndSSO` / 商品区分 `ProdCat`）内の生の週次収益率」
  のローリング相関を使う。グループ分けは呼び出し側（`data_pipeline.preprocess`）が指定する。
- 契約の寿命が株式の52週ローリング窓よりずっと短いことが多いため、既定のウィンドウは
  株式より短い（`graph_params.DERIVATIVE_CORR_WINDOW_SIZE = 8`週）。

ハイパーパラメータ（窓幅・閾値・最小観測数）は全て `scripts/datap/graph/cons.py` の
`graph_params`（`DERIVATIVE_CORR_*` 系）に集約されている。

### `class PeerCorrEdges(NamedTuple)`
ピアグループ内相関エッジの構築結果。
- `edges: Dict[int, List[Tuple[str, str, float]]]` — `week_id -> [(src_code, dst_code, weight), ...]`。相関行列は対称なので `(i,j)` と `(j,i)` の両方向が入っている。

### `_weekly_return(df: pd.DataFrame, code_col: str, close_col: str) -> pd.DataFrame`
- **概要**: `Code` ごとに週次終値（対数値、`AdjC`列）の差分を「収益率」として `ret` 列に付与する。
- **処理内容**: `df.sort_values([code_col, "week_id"])` した後、`groupby(code_col)[close_col].diff()`。

### `build_peer_corr_edges(df, *, group_col, code_col="Code", close_col="AdjC", window=graph_params.DERIVATIVE_CORR_WINDOW_SIZE, threshold=graph_params.DERIVATIVE_CORR_THRESHOLD, min_periods=graph_params.DERIVATIVE_CORR_MIN_PERIODS) -> PeerCorrEdges`
- **概要**: `group_col`（`UndSSO` や `ProdCat`）が同じ契約同士について、週次収益率のローリング相関を計算し、`|corr| > threshold` のペアをエッジ候補として収集する公開API。
- **引数**:
  - `df`: 週次集約済みのオプション/先物DataFrame（`week_id`, `code_col`, `close_col`, `group_col` を含む）。
  - `group_col`: グルーピングキー（オプションなら `"UndSSO"`、先物なら `"ProdCat"`）。
  - `code_col`: 契約の一意なコード列（既定 `"Code"`）。
  - `close_col`: 収益率算出のもとになる終値列（既定 `"AdjC"`、SQL側で `log(C+1)` 変換済みの対数終値）。
- **対象外**: `group_col` がNULLの行（原資産の無い指数・債券オプション等）は事前に除外する。
- **処理内容（本体アルゴリズム）**:
  1. `_weekly_return` で `ret` 列を付与し、`group_col` がNULLの行を除去。
  2. `group_col` のユニーク値ごとにループ（進捗を `\r` で表示）。同一グループ内の契約数が1件以下ならスキップ。
  3. グループごとに `(week_id x Code)` のピボット表 `pivot`（値は `ret`）を作る。列数が1以下ならスキップ。
  4. 「純粋にその週にノード（行）が存在するか」を表す `exists` テーブルを、`ret` とは別に `_present=1` の定数列をピボットして作る（下記★参照）。
  5. 週インデックス `t` ごとに、直近 `window` 週の窓 `[lo, t]` を見て、
     - `active_count`（窓内での `ret` 非NULL回数）が `min_periods` 以上、かつ
     - `exists.iloc[t]` が `True`（＝今週その契約のノードが実在する）
     の両方を満たす契約列 `active_cols` のみに絞り込む。
  6. 絞り込んだ小さな部分行列 `pivot.iloc[lo:t+1][active_cols]` に対して `DataFrame.corr()` を呼び、対角を0にした上で `|corr| > threshold` の要素を `(src_code, dst_code, weight)` として `edges[week_id]` に追加する（対称なので両方向とも追加される）。
- **返り値**: `PeerCorrEdges(edges=...)`。
- **★性能上の設計判断（実装コメント・docstringに詳記）**:
  素朴に「グループ内で過去に一度でも上場した契約」全てを列に持つピボット表に対し
  `rolling().corr()` を呼ぶ実装では、同時に生存している契約が数個〜数十個程度でも
  列数自体は上場・満期を繰り返した契約の総数（オプションでは1原資産あたり最大3,674契約、
  平均約1,050契約が実測値）まで膨れ上がり、`O(週数 × 契約数^2)` の相関計算が
  ボトルネックになる（実測で1グループの計算が数分〜終わらないレベルまで悪化した）。
  そのため上記4〜6のように、各週ごとに「直近`window`週で`min_periods`週以上データがある
  契約」にだけ列を絞り込んでから `DataFrame.corr()` を呼ぶ方式に変更した
  （絞り込み自体は `O(週数 × 契約数)` の `notna` 集計のみで済み、相関計算は
  同時生存契約数だけの小さな正方行列に対して行われる）。同一の5グループ
  （原資産）で検証したところ、素朴な実装ではタイムアウト（120秒超）したのに対し、
  絞り込み版では7.4秒で完了した。
- **★正しさ上の設計判断（`exists` テーブルが必要な理由）**:
  `ret` 列は `diff()` の性質上、契約が上場した最初の週は「行は存在するが値はNaN」になる。
  そのため `notna(pivot)` だけを根拠に「窓内に十分なデータがある契約」を選ぶと、
  「直近数週間はデータが欠けている（＝今週ノードが存在しない）契約」が
  「過去の窓内データ」を根拠に誤って選ばれてしまい、存在しないノードを指す
  ダングリングエッジ（例: `future_202307_168020019` のような、`node`テーブルに
  存在しないnode_idへのエッジ）を生成するバグがあった（`graphDataSet._build_full_graph()`
  の `map_edge_ids_to_idx()` が `KeyError` で検出）。`exists` テーブルで
  「今週その契約の行が実在するか」を別途チェックすることで修正済み。
- **呼び出し元**: `data_pipeline.preprocess.option_corr_option_preprocess()`
  （`group_col="UndSSO"`）、`data_pipeline.preprocess.future_corr_future_preprocess()`
  （`group_col="ProdCat"`）。

---

## 4. cons.py

パス・パラメータ定数を集約するモジュール。ロジックは持たない。`graph_params`（ハイパーパラメータ）と `rel_sql`（パス・SQL取得範囲）の2クラスで構成される。

### `class graph_params`

**新設クラス**。以前は `capm_corr.capm_corr_constants` / `derivative_corr.peer_corr_constants` /
`data_pipeline.py` 直下の複数のモジュール定数に分散していたハイパーパラメータを、
「ユーザーが調整し得るもの」として一箇所に集約したもの。各関数は引数を明示的に
渡さなかった場合にここの値をデフォルトとして参照する。**値を変更する手段は2通り**:
(1) このクラスの値を直接書き換える（恒久的な変更）、(2) 各関数呼び出し時にキーワード
引数で個別に上書きする（その場限りの変更）。

#### stock__corr__stock （CAPM残差相関, capm_corr.py 用）
| 定数 | 型・既定値 | 意味 |
|---|---|---|
| `CAPM_WINDOW_SIZE_FOR_CAPM` | `int = 52` | CAPMをローリング推定する窓（週） |
| `CAPM_WINDOW_SIZE_FOR_CORR` | `int = 52` | CAPM残差リターンのローリング相関を取る窓（週） |
| `CAPM_THRESHOLD` | `float = 0.7` | `\|corr\| > CAPM_THRESHOLD` の銘柄ペアのみエッジ化 |
| `CAPM_FIRST_WEEK_ID` | `int = 201501` | この週ID以降のみ `stock__corr__stock` エッジを生成 |
| `CAPM_RESIDUAL_STORED_PATH` | `str = "./scripts/datap/graph/store/returns_residual_matrix.parquet"` | CAPM残差行列のキャッシュ先 |
| `CAPM_DEVICE` | `Optional[str] = None` | `None`なら呼び出し時に `cuda`使用可否を自動判定 |

#### Option__corr__Option / Future__corr__Future （derivative_corr.py 用）
| 定数 | 型・既定値 | 意味 |
|---|---|---|
| `DERIVATIVE_CORR_WINDOW_SIZE` | `int = 8` | 相関を取るローリング窓（週）。契約寿命が短いため株式(52週)より小さめ |
| `DERIVATIVE_CORR_MIN_PERIODS` | `int = 4` | 窓内で相関を計算するために最低限必要な観測週数 |
| `DERIVATIVE_CORR_THRESHOLD` | `float = 0.7` | `\|corr\| > DERIVATIVE_CORR_THRESHOLD` のペアのみエッジ化。下げるとエッジ数が非線形に急増し得る（同一原資産のオプション間の相関分布の形状次第で、閾値をわずかに下げただけでも桁違いに増加する可能性がある。実測ベースの試算は `claude_output/` 配下の別メモを参照） |

#### Stock__derivative__Future （data_pipeline.py 用）
| 定数 | 型・既定値 | 意味 |
|---|---|---|
| `MARKET_INDEX_FUTURE_PRODCATS` | `List[str] = ["NK225F", "TOPIXF"]` | 全対象銘柄を接続する「主要な株価指数先物」の商品区分 |

#### ノード特徴量・vocab（data_pipeline.py 用）
| 定数 | 型・既定値 | 意味 |
|---|---|---|
| `DEFAULT_VOCAB_DIR` | `str = "scripts/datap/graph/DS/vocab"` | カテゴリ変数vocabの保存先ディレクトリ |
| `TIME_ENCODING_EPOCH` | `str = "2000-01-01"` | Time2Vec等の時間エンコーディングの基準日 |

#### get_loaders（train/val/test split・近傍サンプリング, data_pipeline.py 用）
| 定数 | 型・既定値 | 意味 |
|---|---|---|
| `SPLIT_1_PER` | `float = 0.7` | trainとvalの境界（time_idの範囲に対する割合） |
| `SPLIT_2_PER` | `float = 0.85` | valとtestの境界（time_idの範囲に対する割合） |
| `BATCH_SIZE` | `int = 32` | NeighborLoaderのバッチサイズ |
| `NUM_NEIGHBORS_PER_HOP` | `int = 10` | `num_neighbors`を明示指定しなかった場合、全エッジ種別に一律で使う「1ホップあたりの近傍サンプル数」 |
| `NUM_HOPS` | `int = 2` | NeighborLoaderのホップ数（＝`num_neighbors`のリスト長） |

> `CATEGORICAL_COLUMNS` / `DATE_COLUMNS`（`data_pipeline.py`）はここには含まれない。
> 理由は[1. data_pipeline.pyのコラム](#1-data_pipelinepy)を参照。

### `class rel_sql`

#### DATABASE PATHS
| 定数 | 値 |
|---|---|
| `PATH_ORIGINAL_DB` | `"./db/synthesis/synthesis.duckdb"`（元データDB） |
| `PATH_GRAPHINFO_DB` | `Template("./scripts/datap/graph/DS/graph_info_${serial_id}.duckdb")`（`serial_id` でパラメータ化されたTemplate。`.safe_substitute(serial_id=...)` で実パスに解決する） |

#### SQL FILE PATHS
| 定数 | 値 |
|---|---|
| `PATH_SQL_TO_FETCH_PRICES` | `./scripts/datap/graph/sql/get_table_to_CAPM.sql` |
| `PATH_SQL_TO_FETCH_FINANCIALS` | `./scripts/datap/graph/sql/get_fin_data_by_week.sql` |
| `PATH_SQL_TO_FETCH_OPTIONS` | `./scripts/datap/graph/sql/get_table_to_option.sql`（新設） |
| `PATH_SQL_TO_FETCH_FUTURES` | `./scripts/datap/graph/sql/get_table_to_future.sql`（新設） |
| `PATH_SQL_TO_INSERT_TO_FEATS_TABLE` | `./scripts/datap/graph/sql/insert_to_feats_table.sql` |
| `PATH_SQL_TO_INSERT_TO_NODE_TABLE` | `./scripts/datap/graph/sql/insert_to_node_table.sql` |
| `PATH_SQL_TO_INSERT_TO_EDGE_TABLE` | `./scripts/datap/graph/sql/insert_to_edge_table.sql` |
| `PATH_SQL_TO_CREATE_GRAPHINFO_TABLE` | `./scripts/datap/graph/sql/create_graph_info_table.sql` |

#### SQL PARAMETERS
| 定数 | 値 | 意味 |
|---|---|---|
| `START_WEEK_ID` | `200819` | 取得対象期間の開始週ID（`prices`/`financials`/`options`/`futures` 全てのSQLで `WHERE week_id > $START_WEEK_ID` に使用） |
| `END_WEEK_ID` | `202616` | 取得対象期間の終了週ID |

**参考**: `PATH_GRAPHINFO_DB` が指すDBのスキーマ（`create_graph_info_table.sql`）:
```sql
CREATE OR REPLACE TABLE node(
  node_id VARCHAR NOT NULL, is_target BOOL NOT NULL, ticker VARCHAR,
  node_type VARCHAR NOT NULL, time_id INTEGER NOT NULL
);
CREATE OR REPLACE TABLE edge(
  edge_id VARCHAR NOT NULL, edge_type VARCHAR NOT NULL,
  src_node_id VARCHAR NOT NULL, dst_node_id VARCHAR NOT NULL,
  edge_weight DOUBLE NOT NULL, observable_time_id INTEGER NOT NULL
);
CREATE OR REPLACE TABLE feats(
  node_id VARCHAR NOT NULL, feats JSON NOT NULL, feats_num INTEGER NOT NULL
);
```
`node_type` / `edge_type` は共に自由記述の `VARCHAR` であり、DBスキーマ自体は
`option`/`future` ノードや新設6エッジ種別を追加するにあたって一切変更不要だった
（スキーマがノード・エッジ種別に依存しない設計になっていたため）。
`CREATE OR REPLACE` のため、`create.graph_info()` の再実行は既存テーブルを破棄して作り直す点に注意。

---

## 5. sql.py

DuckDBに対する fetch（取得）/ insert（挿入）/ create（テーブル作成）処理をまとめたモジュール。いずれもSQLファイルを `string.Template` で読み込み、`.safe_substitute()` でパラメータ解決してから `duckdb` 接続経由で実行する。

### `class fetch`

#### `fetch._any(QUERY: str, DB_NAME: str) -> pd.DataFrame`（staticmethod）
- **概要**: 汎用のSELECT実行ヘルパー。`duckdb.connect(DB_NAME)` → `conn.execute(QUERY).df()` → `conn.close()`。
- **返り値**: クエリ結果の `pd.DataFrame`。

#### `fetch.prices() -> pd.DataFrame`（staticmethod）
- **概要**: `sql/get_table_to_CAPM.sql` を読み込み、`cf.START_WEEK_ID` / `cf.END_WEEK_ID` を `safe_substitute` してから `cf.PATH_ORIGINAL_DB`（synthesis.duckdb）に対して実行する。
- **返り値**: 週次OHLCV・リターン・CAPM関連列（`week_id, Code, r_i, r_m, r_f, AdjO/H/L/C/Vo, S33, S17, Mkt, Section_id, Mrgn, y, ...`）を含むDataFrame（SQL側の `WITH` 句で TOPIX・コールレートと結合し週次集計・リターン計算まで完結している）。

#### `fetch.financials() -> pd.DataFrame`（staticmethod）
- **概要**: `sql/get_fin_data_by_week.sql` を読み込み、同様に週ID範囲を置換して `cf.PATH_ORIGINAL_DB` に対して実行する。
- **返り値**: `imp.fin_sum` テーブルから `week_id`（`yearweek(DiscDate)`）と決算関連列を抽出したDataFrame。

#### `fetch.options() -> pd.DataFrame`（staticmethod・新設）
- **概要**: `sql/get_table_to_option.sql` を読み込み、週ID範囲を置換して `cf.PATH_ORIGINAL_DB` に対して実行する。
- **SQLの処理内容**: `imp.drv_opt_tmp`（日次バー）を `yearweek(TradeDate)` で週次集約する。
  - `AdjO/H/L/C`: `first/max/min/last` を取った上で `log(x+1)` 変換（`get_table_to_CAPM.sql` の株式側と同じ命名規則・変換方式に揃えている）。
  - `AdjVo`（出来高）・`AdjVa`（売買代金）・`AdjOI`（建玉）も同様に `log(last(x)+1)`。
  - `UndSSO`: `'-'`（原資産なし）の場合は `NULL` に変換し、それ以外は末尾に `'0'` を付与して `eqt_main.Code` と同じ5桁表記に正規化（4桁の原資産コード → 5桁）。
  - `Moneyness` / `DeviationRate` / `SQRemainingDays` / `IV` はそのまま週内最終値（`last(...)`)。
  - `NULL_TYPE_1` / `NULL_TYPE_2`（欠損マスク）は週内で1件でも立っていれば`1`（`max(...)`）。
- **返り値の列**: `week_id, Code, ProdCat, UndSSO, CM, AdjO, AdjH, AdjL, AdjC, AdjVo, AdjVa, AdjOI, Moneyness, DeviationRate, SQRemainingDays, IV, NULL_TYPE_1, NULL_TYPE_2`。
- **呼び出し元**: `data_pipeline.graphDataSet._ensure_db_built()`。

#### `fetch.futures() -> pd.DataFrame`（staticmethod・新設）
- **概要**: `sql/get_table_to_future.sql` を読み込み、週ID範囲を置換して `cf.PATH_ORIGINAL_DB` に対して実行する。
- **SQLの処理内容**: `imp.drv_ftr`（日次バー、週次集約前）を `yearweek(TradeDate)` で週次集約する。`imp.drv_ftr` には商品区分 `ProdCat` が残っていないため、`raw.drv_ftr` から `Code -> ProdCat` の対応（`Code`ごとに`ProdCat`は不変という前提で `first(ProdCat)` を取得）を別途JOINして補完している。列変換方針（`AdjO/H/L/C/Vo/Va/OI` のlog変換等）はオプション側と同様。
- **返り値の列**: `week_id, Code, ProdCat, CM, AdjO, AdjH, AdjL, AdjC, AdjVo, AdjVa, AdjOI, DeviationRate, SQRemainingDays, NULL_TYPE_1`。
- **呼び出し元**: `data_pipeline.graphDataSet._ensure_db_built()`。

#### `fetch.edge_index(serial_id: int) -> pd.DataFrame`（staticmethod）
- **概要**: `graph_info_{serial_id}.duckdb` の `edge` テーブルから `src_node_id, dst_node_id` を取得する。
- **クエリ**: `SELECT src_node_id, dst_node_id FROM edge`

#### `fetch.edge_attr(serial_id: int, attr_name: str) -> pd.DataFrame`（staticmethod）
- **概要**: `edge` テーブルから任意の1列 `attr_name` を取得する。
- **クエリ**: `SELECT {attr_name} FROM edge`（**f-stringによる直接埋め込み**。`attr_name` はコード内部の固定文字列 `"edge_type"`/`"edge_weight"`/`"observable_time_id"` のみが渡される想定であり、外部入力をそのまま渡す用途では使用されていない）。

#### `fetch.node_attr(serial_id: int, attr_name: str) -> pd.DataFrame`（staticmethod）
- **概要**: `node` テーブルから任意の1列を取得する。`edge_attr` と同様の実装。**現状 `data_pipeline.py` からは未使用**（`node_table` に置き換わっている）。

#### `fetch.node_table(serial_id: int, node_type: str) -> pd.DataFrame`（staticmethod）
- **概要**: `node` テーブルと `feats` テーブルを `node_id` でJOINし、指定 `node_type` の全列を取得する。
- **クエリ**: `SELECT n.*, f.feats FROM node n JOIN feats f ON n.node_id = f.node_id WHERE n.node_type = '{node_type}'`（**f-stringによる直接埋め込み**。`node_type` はコード内部の固定文字列 `"stock"`/`"statement"`/`"option"`/`"future"` のみが渡される想定）。
- **呼び出し元**: `data_pipeline.fetch_node_table()`。

### `class insert`

#### `insert._any(QUERY: str, data_list: pd.DataFrame, serial_id: int) -> None`（staticmethod）
- **概要**: 汎用のINSERT実行ヘルパー。`graph_info_{serial_id}.duckdb` に接続し `conn.execute(QUERY)` を実行して閉じる。
- **注意**: `QUERY` は `"INSERT INTO xxx (SELECT * FROM data_list)"` という形のSQLであり、DuckDBが呼び出しスコープ内のローカル変数 `data_list`（`pd.DataFrame`）をSQLから直接参照できる機能（DuckDBのPython統合によるDataFrame自動認識）を利用している。**このメソッドの引数 `data_list` 自体はSQL文字列には埋め込まれず、DuckDBがローカル変数名 `data_list` をスキャンして解決する**という暗黙の前提がある点に注意（変数名を変更すると壊れる設計）。

#### `insert.edge(data_list: pd.DataFrame, serial_id: int) -> None`（staticmethod）
- **概要**: `sql/insert_to_edge_table.sql`（`INSERT INTO edge (SELECT * FROM data_list)`）を読み込み `insert._any` で実行する。
- **前提**: `data_list` の列順が `edge` テーブルの列定義（`edge_id, edge_type, src_node_id, dst_node_id, edge_weight, observable_time_id`）と一致していること（`SELECT *` のため列名ではなく位置で対応付けられる）。全ての `preprocess` 側の呼び出しは列名を `edge_weight_list`（実体はスカラー値）としているが、位置さえ合っていれば列名自体は問われない。

#### `insert.node(data_list: pd.DataFrame, serial_id: int) -> None`（staticmethod）
- **概要**: `sql/insert_to_node_table.sql` を使い `node` テーブルへ挿入する。列順は `node_id, is_target, ticker, node_type, time_id` と一致させる必要がある。

#### `insert.feats(data_list: pd.DataFrame, serial_id: int) -> None`（staticmethod）
- **概要**: `sql/insert_to_feats_table.sql` を使い `feats` テーブルへ挿入する。列順は `node_id, feats, feats_num` と一致させる必要がある。

### `class create`

#### `create.graph_info(serial_id: int) -> None`（staticmethod）
- **概要**: `graph_info_{serial_id}.duckdb` に接続し、`sql/create_graph_info_table.sql` を実行して `node` / `edge` / `feats` の3テーブルを作成する。
- **注意**: SQLが `CREATE OR REPLACE TABLE` のため、既存DBに対して呼ぶと中身が全て破棄される（`data_pipeline.graphDataSet._ensure_db_built()` はDBファイルの存在チェックでガードしているため、通常運用でこの破壊的動作は踏まない設計になっている）。

---

## 6. main.py

```python
import scripts.datap.graph.data_pipeline as dt_pipe
```

- **概要**: 現状 `data_pipeline` モジュールをインポートするのみで、実行コードは存在しない（**未実装のエントリポイント／スタブ**）。
- **想定用途**: 将来的にCLI引数を受け取り、`dt_pipe.get_loaders(...)` や `dt_pipe.mock_code(...)` 等を呼び出すエントリポイントとして拡張される見込み。現時点で `python -m scripts.datap.graph.main` を実行しても副作用は発生しない。

---

## 付録: 関数呼び出し関係（主要フロー）

```
main.py (未実装)
  └─ (将来的に) data_pipeline.get_loaders / mock_code

data_pipeline.get_loaders()
  └─ graphDataSet.__init__()
       ├─ _allow_numpy_globals_for_torch_load()
       └─ InMemoryDataset.__init__() [PyG標準]
            └─ process()  ※ processed_paths[0] が無い場合のみPyGが自動呼び出し
                 ├─ _ensure_db_built()
                 │    ├─ sql.create.graph_info()
                 │    ├─ sql.fetch.financials() / sql.fetch.prices()
                 │    ├─ sql.fetch.options() / sql.fetch.futures()
                 │    └─ preprocess(...).insert_to_graph_info_table()
                 │         ├─ statement_prev_statement_preprocess()   ─ sql.insert.edge()
                 │         ├─ statement_report_stock_preprocess()     ─ sql.insert.edge()
                 │         ├─ stock_corr_stock_preprocess()            ─ capm_corr.build_firm_corr_edges()
                 │         │                                            ─ sql.insert.edge()
                 │         ├─ option_corr_option_preprocess()          ─ derivative_corr.build_peer_corr_edges()
                 │         │                                            ─ _insert_peer_corr_edges() ─ sql.insert.edge()
                 │         ├─ option_prev_option_preprocess()          ─ _prev_chain_preprocess() ─ sql.insert.edge()
                 │         ├─ future_corr_future_preprocess()          ─ derivative_corr.build_peer_corr_edges()
                 │         │                                            ─ _insert_peer_corr_edges() ─ sql.insert.edge()
                 │         ├─ future_prev_future_preprocess()          ─ _prev_chain_preprocess() ─ sql.insert.edge()
                 │         ├─ stock_derivative_option_preprocess()     ─ sql.insert.edge()
                 │         ├─ stock_derivative_future_preprocess()     ─ sql.insert.edge()
                 │         ├─ node_id_define()                        ─ sql.insert.node()
                 │         ├─ build_category_vocabs()                 ─ save_vocab()
                 │         └─ node_feats_define()                     ─ load_vocab() / sql.insert.feats()
                 └─ _build_full_graph()
                      ├─ fetch_node_table() ×4 (stock/statement/option/future) ─ sql.fetch.node_table()
                      ├─ build_node_id_to_idx() ×4
                      ├─ fetch_edge_index() ─ sql.fetch.edge_index()
                      ├─ fetch_edge_attr()  ─ sql.fetch.edge_attr()
                      └─ map_edge_ids_to_idx() ×エッジ種別数（+ REVERSE_RELATIONS 分の逆エッジ）
  └─ NeighborLoader ×3 (train/val/test)
```
