# NeighborLoaderバッチ（HeteroData）出力の読み方

対象: `get_loaders()` が返す `train_loader` / `val_loader` / `test_loader` から
`for batch in loader: print(batch)` のように取り出した際に表示される
`HeteroData(...)` 形式の出力（`test_temp.py` の `mock_code(serial_id=9999)`
がまさにこれを行っている）。

`mock_code()` は3つのローダー（train/val/test）それぞれについて
「1エポック分の全バッチ」を `for batch in loader:` で回して都度 `print(batch)`
しているだけなので、バッチサイズ（`batch_size=32`、質問例では `batch_size=9`
に見えるのは末尾の端数バッチ）の数だけ同じ形式の出力が繰り返し表示される。
**「繰り返される」のはバグではなく、単にローダーの中身を全部printしているため**。

---

## 1. まず大前提：`field=[a, b]` は「値」ではなく「テンソルの形」

PyTorch Geometric（PyG）の `repr()` は、中身の値ではなく **テンソルのshape**
を `[...]` で表示する。これを取り違えると誤読しやすいので最初に明記する。

```
x=[47, 12]              # 形状 (47, 12) の float テンソル（47ノード×12次元特徴量）
num_sampled_edges=[2]   # 形状 (2,) の整数テンソル（＝ホップ数2の内訳が2個入っている）
```

`num_sampled_edges=[2]` は「値が2」という意味では **ない**。`num_neighbors`
に `[10, 10]`（2ホップ）を指定しているため、「1ホップ目で採用したこのエッジ種別の
本数」「2ホップ目で採用した本数」の2要素からなるベクトルである、という意味。
同様に `num_sampled_nodes=[3]` は「(seedとして最初から入っていた数,
1ホップ目で新規追加された数, 2ホップ目で新規追加された数)」の3要素ベクトル
（2ホップ sampling なので「層」は 0, 1, 2 の3つ）。

---

## 2. `HeteroData` 全体の構造

`HeteroData` は「ノードタイプごとの辞書」と「エッジタイプ(src, rel, dst)ごとの辞書」
の集合体。今回のグラフは4ノードタイプ・12エッジタイプなので、
1バッチにつき最大 4 + 12 = 16 個のブロックが表示され得る
（该当データが0件のタイプはブロック自体は出るが `edge_index=[2, 0]` のように空になる）。

```
HeteroData(
  <node_type 1>={ ... },
  <node_type 2>={ ... },
  ...
  (<src>, <rel>, <dst>)={ ... },
  ...
)
```

`get_loaders()` の `NeighborLoader` は `input_nodes=("stock", mask)` を
起点にしているため、**`stock` だけが「サンプリングの種（シード）」であり、
他の3タイプ（statement/option/future）は `stock` から辿り着いた近傍としてのみ
バッチに入る**。

---

## 3. ノードタイプ側ブロックの各フィールド

例: `stock={ x=[47,12], cat_x=[47,5], date_x=[47,0], is_target=[47], time_id=[47], n_id=[47], num_sampled_nodes=[3], input_id=[9], batch_size=9 }`

| フィールド | 意味 |
|---|---|
| `x` | 連続値特徴量（`feats.cont`）。`(このタイプのバッチ内ノード数, 連続値特徴量数)`。`stock`は12次元、`option`は13次元、`future`は10次元、`statement`は55次元 — 各ノードタイプの生データの列数の違いをそのまま反映している。 |
| `cat_x` | カテゴリ特徴量の整数ID（`feats.cat`、`CATEGORICAL_COLUMNS`で定義した列）。列数は `stock`=5（S33/S17/Section_id/Mkt/Mrgn）、`statement`=1（CurPerType）、`option`=3（ProdCat/UndSSO/CM）、`future`=2（ProdCat/CM）。モデル側で列ごとに `nn.Embedding` する想定。 |
| `date_x` | 日付特徴量（経過日数）。`DATE_COLUMNS`に列挙されているのは`statement`の`CurFYEn`のみなので、`statement`だけ`date_x=[N,1]`、他は`date_x=[N,0]`（列が0本）になる。 |
| `is_target` | 損失計算・予測対象かどうかのbool。`stock`のみ `Mkt in {'0000','0500'}` に基づき True/False が混在し得る。`statement`/`option`/`future` は `node_id_define()` で常に `False` を入れているので、**このバッチに限らず全期間・全ノードで常に全件False**（想定通りの挙動）。 |
| `time_id` | このノードの週ID（`week_id`）。 |
| `n_id` | このノードタイプについて、**グラフ全体（HeteroData全体）における通し番号（グローバルインデックス）**。`dataset.load_node_str_id(node_type)[n_id]` で元の文字列 `node_id`（例: `stock_202320_13010`）に逆引きできる。 |
| `num_sampled_nodes` | 層（0ホップ目=シード, 1ホップ目, 2ホップ目, ...）ごとに**新規追加**されたノード数の内訳（§1参照）。要素数は `num_neighbors` のホップ数+1。 |
| `input_id` | **シードタイプ（`stock`）にのみ出現**。`train_mask`/`val_mask`/`test_mask` でマスクされたノード集合の中で、このバッチとして選ばれたノードのグローバルインデックス。 |
| `batch_size` | **シードタイプ（`stock`）にのみ出現**。`len(input_id)`。DataLoaderの`batch_size=32`で指定した数（最終バッチは端数で少なくなる。例の`9`はこのケース）。 |

`n_id` の先頭 `batch_size` 件が `input_id` と同じ並びのシードノード自身であり、
残りが1〜2ホップ目で辿り着いた近傍ノード、という順序になっている。

---

## 4. エッジタイプ側ブロックの各フィールド

例: `(option, corr, option)={ edge_index=[2,17], edge_weight=[17], edge_time=[17], e_id=[17], num_sampled_edges=[2] }`

| フィールド | 意味 |
|---|---|
| `edge_index` | `(2, E)` のLongTensor。`[0]`行が送信元ノードの**バッチ内ローカルインデックス**（`n_id`の添字であり、グローバルindexではない点に注意）、`[1]`行が宛先ノードのローカルインデックス。 |
| `edge_weight` | このエッジの重み（相関係数、または `prev`/`report`/`derivative` 系は一律`1.0`）。 |
| `edge_time` | `observable_time_id`（週ID）。 |
| `e_id` | グラフ全体（DB上の `edge` テーブル）における、このエッジの通し番号。 |
| `num_sampled_edges` | 層（1ホップ目, 2ホップ目, ...）ごとに、このエッジ種別が何本サンプリングされたかの内訳（§1参照）。 |

`(future, rev_derivative, stock)` のように、`REVERSE_RELATIONS` で
自動生成された逆方向エッジも独立したブロックとして表示される
（`(stock, derivative, future)` とは別物として、逆向きに辿った際の
本数が別途カウントされる）。

---

## 5. 質問の出力例を数値で追う

質問に貼られた出力は「`stock` を起点に `batch_size=9` 件をシードとして
2ホップ（`num_neighbors=[10,10]`、全12関係共通）サンプリングした結果」。

- `stock`: シード9件 → 2ホップの探索で最終的に47件まで拡張
  （corr/rev_report/rev_derivative経由で他のstock/statement/futureから
  折り返して辿り着いたstockノードも含む）。
- `option`: `stock`は`option`への直接エッジ（`stock, derivative, option`）を
  持つので1ホップ目で`option`に到達し、そこからさらに
  `option__corr__option`/`option__prev__option`で2ホップ目に広がり、
  最終的に72件。
- `future`: 同様に`stock, derivative, future`経由で1ホップ目に到達するが、
  `stock_derivative_future_preprocess`は主要指数先物（`NK225F`/`TOPIXF`）
  の**期近物2本前後**にしか繋がないため、`option`ほど広がらず9件にとどまっている。
- `option__corr__option`=17本、`future__corr__future`=5本 と、
  `derivative`系（20本、20本）や`prev`系（20本、2本）に比べて少なめなのは、
  相関エッジが`|corr|>0.7`のしきい値でフィルタされた疎なエッジだから
  （設計通りの挙動。詳細は
  [derivative_nodes_edges_implementation.md](derivative_nodes_edges_implementation.md)
  の「4. derivative_corr.py の設計」を参照）。

---

## 6. 現時点で見えている懸念事項

コード上のバグではなく、**モデル設計・ハイパーパラメータとして今後意識した方が
よい点**が2つある。

### 6.1 `stock, derivative, future` はハブ構造になっている

`Stock__derivative__Future` は「その週の全対象銘柄」を「主要株価指数先物の
期近物（`NK225F`/`TOPIXF`、通常各1本）」へ一律接続する設計（ユーザー確認済みの
"market backbone" 方針）。これは裏を返すと、`future`側から見た
`rev_derivative`（future→stock）の次数は**その週の対象銘柄数と同程度
（数百〜数千）**になる。

現在 `num_neighbors` は全関係共通で `[10, 10]` としているため、
`future`ノードを経由して2ホップ目に辿り着く`stock`ネイバーは、
数百〜数千件の中からランダムに10件だけがサンプリングされる。
これは「予測対象銘柄と直接関係のない銘柄」が市場共通シグナル経由で
ノイズとして混入する可能性がある一方、意図通り「市場全体の情報を
集約するハブ」として機能する可能性もあり、**良し悪しは学習結果を見て
判断する必要がある**。気になる場合は `future, rev_derivative, stock` の
`num_neighbors` だけ別途小さくする／0にする（＝derivativeエッジは
stock→future方向の一方向集約のみ使う）といった調整も可能。

### 6.2 `num_neighbors` が12関係すべて `[10, 10]` 均一である

`option__prev__option`（同一契約なら必ず1本）のような密なチェーンと、
`option__corr__option`（しきい値0.7でフィルタされた疎なエッジ）のような
疎な関係が、同じ「各ホップ最大10件」という設定でサンプリングされている。
関係ごとの実際のエッジ密度に応じて`num_neighbors`を関係別にチューニングする
余地がある（`get_loaders()`の`num_neighbors`引数で関係ごとに上書き可能）。

上記2点は「実装のバグ」ではなく、いずれも今回追加した6関係を実際に
学習ループで使う際のハイパーパラメータ選定上の論点として記録している。
