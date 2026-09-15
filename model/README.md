# model/ ディレクトリの運用ルールとグラフデータリファレンス

このファイルは、GNN モデルを実装する際に毎回調べ直すことになりがちな
「`HeteroData` の構造」「ラベルの扱い方」「既知の落とし穴」をまとめた参照ドキュメント。
`model/baseline/` を実装した際に実データ（`serial_id=9999`）で実際に検証した内容が元になっている。

## ディレクトリ構成のルール

モデルごとに `model/<model-alias>/` 以下にファイルを分ける（例: `model/baseline/model.py`,
`model/baseline/train.py`）。共通の知見はこの `model/README.md` に集約し、各モデルの
コード側にはモデル固有の設計判断だけを書く。

### モデル構造の可視化

`model/common/visualize.py` の `write_model_structure_md()` を使うと、構築したモデル
インスタンスのモジュール階層（`named_children()` で辿れる静的な木構造。実際の forward
計算グラフではない）を Mermaid フローチャートとして `model/<alias>/model_structure.md`
に書き出せる。新しく `model/<alias>/train.py` を作る際は、モデルをインスタンス化した
直後に以下を呼ぶ運用にする（`model/baseline/train.py` が実装例）:

```python
from model.common.visualize import write_model_structure_md

model = SomeModel(...).to(device)
write_model_structure_md(model, out_dir=Path(__file__).parent)
```

`model_structure.md` は学習実行のたびに上書きされる自動生成物だが、モデル構造を素早く
目視確認できるようテキストファイルとしてリポジトリにコミットする想定（`.duckdb`/`.pt`
等と違い軽量なので `.gitignore` の対象にはしていない）。

### 起動コマンドの規約

`model/<alias>/train.py` は `model/<alias>/` がそのまま Python パッケージパスになる
（`__init__.py` は置かない namespace package）ため、どのモデルも共通の形で起動できる:

```bash
uv run python -m model.<alias>.train [--options]
```

例（`model/baseline/`）:

```bash
uv run python -m model.baseline.train --serial-id 9999 --epochs 20
```

新しいモデルを追加する際は `argparse` の引数を以下の2グループに分けて実装する:

- **共通引数**（全モデルで名前・意味を揃える）: `--serial-id`（学習に使う `HeteroData` の
  serial id）、`--epochs`。TensorBoard 連携を入れるモデルは `--log-dir`
  （既定 `logs/tensorboard`）・`--run-name`・`--no-tensorboard` も揃える
  （`model/baseline/train.py` が実装例。ログ出力先や無効化フラグの意味を
  モデルごとに変えると `uv run tensorboard --logdir logs/tensorboard` で全モデルの
  実行を横断比較できなくなる）。
- **モデル固有引数**: `--hidden-dim`/`--num-layers`/`--lr`/`--dropout`/`--batch-size` 等の
  ハイパーパラメータは各モデルの設計に応じて自由に追加・変更してよい。

別ターミナルで学習曲線を監視する場合（TensorBoard 連携ありのモデル共通）:

```bash
uv run tensorboard --logdir logs/tensorboard
```

## 入力データ: `HeteroData` の構造

グラフは `scripts/datap/graph/data_pipeline.py` の `graphDataSet` が構築する。
学習・検証・評価用のミニバッチは同モジュールの `get_loaders()` から取得する
（下記「データのロード方法」参照）。グラフ自体は分割されておらず、
`train/val/test` は `stock` ノードの `time_id` に対するマスクとして表現される。

### ノードタイプ（4種）

| node_type | 由来 | is_target | `x`(cont) 次元 | `cat_x` 列（`CATEGORICAL_COLUMNS` 順） | `date_x` 列 |
|---|---|---|---|---|---|
| `stock` | `fetch.prices()`（週次集計） | `Mkt in {"0000","0500"}` の行のみ `True` | 11 | `S33, S17, Section_id, Mkt, Mrgn`（5列） | なし |
| `statement` | `fetch.financials()` | 常に `False` | 55 | `CurPerType`（1列） | `CurFYEn`（1列） |
| `option` | `fetch.options()`（週次集計） | 常に `False` | 13 | `ProdCat, UndSSO, CM`（3列） | なし |
| `future` | `fetch.futures()`（週次集計） | 常に `False` | 10 | `ProdCat, CM`（2列） | なし |

`serial_id=9999` の実データで（`y`/`y_valid` をラベル分離する修正より前に）確認した実際のノード数と
shape（ノード数自体は他の `serial_id` でも期間・件数が変わるだけで同じ考え方。列構成・列順は
`CATEGORICAL_COLUMNS`/`DATE_COLUMNS`/`LABEL_COLUMNS`（`data_pipeline.py`）を変更しない限り変わらない）。
**`stock.x` の次元数はラベル分離修正で 12→11 になった**（旧: `y` が cont 末尾に混入していた、
新: `y`/`y_valid` は `data["stock"].y` / `data["stock"].y_valid` として別テンソル）。
既存の `scripts/datap/graph/DS/processed/data_9999_full.pt` と
`scripts/datap/graph/DS/graph_info_9999.duckdb` は旧スキーマのまま残っているため、
この修正を反映するには一度削除して再構築する必要がある:

```
stock:     x=[3307035, 11]  cat_x=[3307035, 5]  date_x=[3307035, 0]  (旧: x次元12。yがcontに混入)
statement: x=[212340, 55]   cat_x=[212340, 1]   date_x=[212340, 1]
option:    x=[9348313, 13]  cat_x=[9348313, 3]  date_x=[9348313, 0]
future:    x=[62840, 10]    cat_x=[62840, 2]    date_x=[62840, 0]
```

（`HeteroData`/`NeighborLoader` の repr に出る `x=[N, D]` はテンソルの **shape** であって値ではない点に注意。
CLAUDE.md にも同じ注記がある。）

全ノードは共通で `is_target: bool`、`time_id: long`（= 週ID）を持つ。文字列 ID（例:
`stock_202320_13010`）は `HeteroData` には入っておらず、
`dataset.load_node_str_id(node_type)[batch[node_type].n_id]` で別途引く。

### エッジタイプ（9種 + 自動生成される逆方向3種 = 12種）

`REVERSE_RELATIONS`（`data_pipeline.py`）に登録された関係だけ、逆方向エッジが自動生成される
（対称な `corr` 系は登録されておらず、両方向とも同じ relation 名で1本のエッジとして入る）。

| src | rel | dst | 意味 | 自動生成される逆エッジ |
|---|---|---|---|---|
| stock | corr | stock | CAPM残差の52週ローリング相関（`\|corr\|>0.7`）＋同一銘柄の前週チェーン | なし（対称） |
| statement | prev | statement | 同一企業の前期→当期 | なし |
| statement | report | stock | 決算ノード→対応する銘柄週ノード | `(stock, rev_report, statement)` |
| option | corr | option | 同一原資産（`UndSSO`）オプション間のローリング相関 | なし（対称） |
| option | prev | option | 同一契約の前週→当週 | なし |
| future | corr | future | 同一`ProdCat`先物間のローリング相関 | なし（対称） |
| future | prev | future | 同一契約の前週→当週 | なし |
| stock | derivative | option | 銘柄→その銘柄を原資産とするオプション | `(option, rev_derivative, stock)` |
| stock | derivative | future | 全 is_target 銘柄 → 主要指数先物（`NK225F`/`TOPIXF`）の期近物（backbone） | `(future, rev_derivative, stock)` |

実データで確認した `data.edge_types`（順不同、上記12種と一致）:
```
[('future','corr','future'), ('future','prev','future'),
 ('option','corr','option'), ('option','prev','option'),
 ('statement','prev','statement'), ('statement','report','stock'),
 ('stock','rev_report','statement'), ('stock','corr','stock'),
 ('stock','derivative','future'), ('future','rev_derivative','stock'),
 ('stock','derivative','option'), ('option','rev_derivative','stock')]
```

全エッジが `edge_weight`（相関係数、または prev/report/derivative は一律 1.0）と
`edge_time`（`observable_time_id` = 週ID）を持つ。`stock, future` 間の `derivative` は
全 is_target 銘柄が同じ1〜2本の先物に集中接続する **hub** になっており、次数が数百〜数千に
達することがある（`NeighborLoader` のサンプリング数をこの関係だけ絞ることを検討する価値がある）。

### ラベル（重要・要注意）

**予測対象ラベル `y` は `stock.x` には入っていない。** `data["stock"].y`（0/1, 翌週リターンが
正かどうか）として `x` とは完全に分離されたテンソルで持たせている。
`get_table_to_CAPM.sql` で `lag(r_i, -1) OVER w AS r_i_next, if(r_i_next>0, 1, 0) AS y` として
計算され、`data_pipeline.py` の `LABEL_COLUMNS = {"stock": ["y", "y_valid"]}` に登録された
列は `node_feats_define()` の `cont_cols` から必ず除外される
（登録漏れで `cont_cols` に "y"/"y_*" 列が残っていた場合は `ValueError` で構築時に検出される
安全弁も入っている）。

かつて `y` が `stock.x` の末尾列に紛れ込んでいた時期があり（バグ、修正済み）、
その名残でモデル側に列位置を手で切り離すコードが残っていることがあるので注意。
現行の正しい使い方は:

```python
labels = batch["stock"].y.long()  # data_pipeline.py が x とは別に生やしている
logits = model(batch)  # batch["stock"].x にはラベルは一切含まれない
```

`model/baseline/train.py` の `stock_labels()` が実装例。

**`y_valid`（ラベルが定義可能かどうか）**: 各銘柄の最終観測週は `r_i_next` が NULL になるため、
DuckDB の `if(NULL, 1, 0)` は else 分岐（0）を返し、`y=0` と「実際に下落」が区別できない。
この区別のために `data["stock"].y_valid`（bool）を持たせてあり、`y_valid=False` の週は
ラベルが意味的に不定である。`get_loaders()` は `is_target & y_valid` を train/val/test
マスクの条件に含めているため、`get_loaders()` 経由で取得した seed ノードには
このマスク処理が既に適用済みで、`y_valid=False` のノードは学習・評価に登場しない
（`graphDataSet` を直接使って全ノードを見る場合は自分でこのマスクをかけること）。

### 既知の欠損値（NaN）

`stock` の `r_i`（cont_cols の9番目、index 8）は各銘柄の上場直後の最初の週で
前週終値が存在しないため NaN になる（`serial_id=9999` で 3,307,035 行中 3,163 行）。
他のノードタイプ・他の列に NaN/Inf は無いことを確認済み。

`LayerNorm`/`BatchNorm` はこの NaN を行全体に伝播させ、メッセージパッシングで
さらに近傍ノードにも広がるため、数バッチで loss が NaN になる（実際に踏んだ）。
モデル側の特徴量エンコーダで `torch.nan_to_num(x)` してから正規化・線形層に通すこと。

### 特徴量の値スケール

`x` は列ごとに正規化されていない生の値（log株価、出来高、財務諸表の生数値など）が
そのまま入っている。何も考えずに `Linear` に通すと出力がオーバーフローし
loss が発散する（実際に発生: 初期 loss が 76 まで跳ねた）。`LayerNorm` を
`cont`/`date` 特徴量に対して事前にかけると ln(2)≈0.69 付近の妥当な初期値に収まることを確認済み。

## データのロード方法

```python
from scripts.datap.graph.data_pipeline import (
    get_loaders, graphDataSet, CATEGORICAL_COLUMNS, get_vocab_sizes,
)

train_loader, val_loader, test_loader = get_loaders(serial_id=9999, batch_size=32)
data = train_loader.data  # 3つの loader は同一の HeteroData を共有（マスクのみ異なる）
```

- `graphDataSet(root="scripts/datap/graph/DS", serial_id=...)` を直接使う必要はない
  （`get_loaders` 内部で構築済み。`NeighborLoader` は `.data` 属性に元の `HeteroData` を保持している）。
- 既存の構築済みグラフ（`serial_id=9999`）が `scripts/datap/graph/DS/processed/data_9999_full.pt`
  として既に存在するため、プロトタイピングはこれを再利用できる（再構築不要）。
- `NeighborLoader` はミニバッチの**起点（seed）ノードを各ノードタイプ配列の先頭に置く**。
  損失・精度は `batch["stock"].batch_size` 件分の先頭だけで計算する
  （`option`/`statement`/`future` は常に近傍としてのみ登場し、seed にはならない）。
- カテゴリ列の vocab サイズは `get_vocab_sizes(serial_id, node_type)` で取得できる
  （`{列名: vocab数}` の dict。列順は `CATEGORICAL_COLUMNS[node_type]` と一致するため
  `[vocab_sizes[c] for c in CATEGORICAL_COLUMNS[node_type]]` で `cat_x` の列順と揃う）。
  `serial_id=9999` での実測値: `stock=[35,19,9,12,4]`, `statement=[5]`,
  `option=[5,242,220]`, `future=[14,224]`。

## 関連する主要ハイパーパラメータ（`scripts/datap/graph/cons.py` の `graph_params`）

グラフ構築側（相関の閾値・ウィンドウ、split比率、NeighborLoader既定値）はここに集約されている。
モデル側の独自ハイパラ（hidden_dim、層数、lr等）は各 `model/<alias>/` 側で管理する。

- `SPLIT_1_PER=0.7`, `SPLIT_2_PER=0.85`（train/val/test の時系列分割点）
- `BATCH_SIZE=32`, `NUM_NEIGHBORS_PER_HOP=10`, `NUM_HOPS=2`（`get_loaders` の既定値）

## 実装例: `model/baseline/`

最も単純な GNN ベースライン。`HeteroConv` + `GraphConv`（`edge_weight` を使う重み付き
メッセージパッシング）を使い、上記のラベル分離・NaN処理・LayerNorm正規化を全て織り込み済み。
新しいモデルを作る際の最小構成の参考実装として使える。
