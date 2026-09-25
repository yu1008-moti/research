# Scaling GNNs via Neighbor Sampling

- [Scaling GNNs via Neighbor Sampling](#scaling-gnns-via-neighbor-sampling)
  - [Neighbor Sampling](#neighbor-sampling)
  - [Basic Usage](#basic-usage)
  - [Hierarchical Extension](#hierarchical-extension)
  - [Advanced Options](#advanced-options)

---

グラフニューラルネットワーク（GNN）が抱える課題の1つは，例えば産業応用やソーシャルアプリケーションのように，大規模なグラフへスケールさせることである．
従来の深層ニューラルネットワークは，学習損失を個々のサンプル（*ミニバッチ* と呼ばれる）へ分解し，勾配を確率的に近似することで，大量のデータへ十分にスケールすることが知られている．
一方で，GNN において確率的なミニバッチ学習を適用することは難しい．なぜなら，あるノードの埋め込みはその近傍すべての埋め込みに再帰的に依存しており，レイヤー数に対して指数的に増加するノード間の高い相互依存性が生じるためである．
この現象はしばしば *neighbor explosion*（近傍爆発）と呼ばれる．
単純な回避策として，GNN は通常フルバッチ方式で実行される（例として[こちら](https://github.com/pyg-team/pytorch_geometric/blob/master/examples/gcn.py)を参照）．この方式では，GNN はすべてのレイヤーにおいてすべての隠れノード表現にアクセスできる．
しかし，これはメモリの制約と収束の遅さから，大規模グラフでは実行不可能である．

ミニバッチ学習によって引き起こされる neighbor explosion 問題を緩和するために，すなわち **ノード単位（node-wise）**，**レイヤー単位（layer-wise）**，**部分グラフ単位（subgraph-wise）** のサンプリング手法や，**伝播（propagation）と予測（prediction）を分離する** ために，スケーラビリティ技術は大規模グラフへ GNN を適用する上で不可欠である．
このチュートリアルでは，[“Inductive Representation Learning on Large Graphs”](https://arxiv.org/abs/1706.02216) 論文で最初に導入された，最も一般的なノード単位のサンプリング手法について詳しく見ていく．

## Neighbor Sampling

PyG は，[`torch_geometric.loader.NeighborLoader`](../modules/loader.html#torch_geometric.loader.NeighborLoader) クラスを通じて近傍サンプリングを実装している．
近傍サンプリングは，ノード $v \in \mathcal{V}$ に対して高々 $k$ 個の固定数の近傍を再帰的にサンプリングする，すなわち $\tilde{\mathcal{N}}(v) \subset \mathcal{N}(v)$（ただし $|\tilde{\mathcal{N}}| \le k$）とすることで動作し，全体として $\mathcal{O}(k^L)$ に有界な $L$-hop 近傍サイズをもたらす．
つまり，シードノードの集合 $\mathcal{B} \subset \mathcal{V}$ から出発し，$\mathcal{B}$ 内の各ノード $v$ について高々 $k$ 個の近傍をサンプリングし，続いて前の hop でサンプリングされた各ノードについて近傍をサンプリングする，という処理を繰り返す．
得られるグラフ構造は，$\mathcal{B}$ 内の各ノード $v$ を中心とした **有向** $L$-hop 部分グラフを保持しており，すべてのノードは $\mathcal{B}$ 内の少なくとも1つのシードノードへ，高々 $L$ の長さのパスを少なくとも1つ持つことが保証される．
そのため，$L$ 層を持つメッセージパッシング GNN は，サンプリングされたノード全体をその計算グラフに組み込むことになる．

[](../_images/neighbor_loader.png)

重要な点として，近傍サンプリングはあくまで neighbor explosion 問題をある程度緩和できるにすぎない．なぜなら，レイヤー数の増加に伴い全体の近傍サイズは依然として指数的に増加するためである．
その結果，2〜3回を超えるイテレーションのサンプリングは一般的に現実的ではない．

多くの場合，サンプリングする hop 数とメッセージパッシング層の数は同期して保たれる．
具体的には，メッセージパッシング層の数よりも多くの hop をサンプリングすることは非常に無駄である．なぜなら，GNN は後の hop でサンプリングされたノードの特徴を，シードノードの最終的なノード表現に決して組み込むことができないからである．
とはいえ，より深い GNN を利用することも可能ではあるが，その場合はサンプリングされた部分グラフを双方向（bidirectional）版に変換し，正しいメッセージパッシングの流れを保証するよう注意する必要がある．
PyG は [`NeighborLoader`](../modules/loader.html#torch_geometric.loader.NeighborLoader) の追加の引数を通じてこれをサポートしており，他のミニバッチ手法，例えば [`ClusterLoader`](../modules/loader.html#torch_geometric.loader.ClusterLoader)，[`GraphSAINTSampler`](../modules/loader.html#torch_geometric.loader.GraphSAINTSampler)，[`ShaDowKHopSampler`](../modules/loader.html#torch_geometric.loader.ShaDowKHopSampler) は，このユースケースに対して標準で対応するよう設計されている．

## Basic Usage

> **Note**
>
> このセクションでは，PyG の [`Node2Vec`](../generated/torch_geometric.nn.models.Node2Vec.html#torch_geometric.nn.models.Node2Vec) クラスを使って，単一のグラフに対してミニバッチ方式で GNN を学習する方法を学ぶ．大規模な実世界データを用いた完全に動作するサンプルは，[examples/reddit.py](https://github.com/pyg-team/pytorch_geometric/blob/master/examples/reddit.py) にある．

[`NeighborLoader`](../modules/loader.html#torch_geometric.loader.NeighborLoader) は，PyG の [`Data`](../generated/torch_geometric.data.Data.html#torch_geometric.data.Data) オブジェクトまたは [`HeteroData`](../generated/torch_geometric.data.HeteroData.html#torch_geometric.data.HeteroData) オブジェクトから初期化され，サンプリングの実行方法を次のように定義する．

- `input_nodes`：サンプリングを開始するシードノードの集合を定義する．
- `num_neighbors`：各 hop において各ノードに対してサンプリングする近傍数を定義する．
- `batch_size`：一度に考慮するシードノードの数を定義する．
- `replace`：復元抽出するか非復元抽出するかを定義する．
- `shuffle`：各エポックでシードノードをシャッフルするかどうかを定義する．

```python
import torch
from torch_geometric.data import Data
from torch_geometric.loader import NeighborLoader

x = torch.randn(8, 32)  # Node features of shape [num_nodes, num_features]
y = torch.randint(0, 4, (8, ))  # Node labels of shape [num_nodes]
edge_index = torch.tensor([
    [2, 3, 3, 4, 5, 6, 7],
    [0, 0, 1, 1, 2, 3, 4]],
)

#   0  1
#  / \/ \
# 2  3  4
# |  |  |
# 5  6  7

data = Data(x=x, y=y, edge_index=edge_index)

loader = NeighborLoader(
    data,
    input_nodes=torch.tensor([0, 1]),
    num_neighbors=[2, 1],
    batch_size=1,
    replace=False,
    shuffle=False,
)
```

ここでは，最初の2つのノードに対して部分グラフをサンプリングするために `NeigborLoader` を初期化しており，第1 hop で2つの近傍を，第2 hop で1つの近傍をサンプリングしたいとする．
`batch_size` は `1` に設定されているため，`input_nodes` はサイズ `1` のチャンクに分割される．

[`NeighborLoader`](../modules/loader.html#torch_geometric.loader.NeighborLoader) の実行では，シードノード `0` が第1 hop でノード `2` と `3` をサンプリングすることが期待される．第2 hop では，ノード `2` がノード `5` を，ノード `3` がノード `6` をサンプリングする．
`loader` の出力を見て確認してみよう．

```python
batch = next(iter(loader))

batch.edge_index
>>> tensor([[1, 2, 3, 4],
            [0, 0, 1, 2]])

batch.n_id
>>> tensor([0, 2, 3, 5, 6])

batch.batch_size
>>> 1
```

[`NeighborLoader`](../modules/loader.html#torch_geometric.loader.NeighborLoader) は，次の属性を含む [`Data`](../generated/torch_geometric.data.Data.html#torch_geometric.data.Data) オブジェクトを返す．

- `batch.edge_index`：部分グラフのエッジインデックスを含む．
- `batch.n_id`：サンプリングされたすべてのノードの元のノードインデックスを含む．
- `batch.batch_size`：シードノード数（バッチサイズ）を含む．

さらに，ノード特徴とエッジ特徴は，それぞれサンプリングされたノード/エッジの特徴のみを含むようにフィルタリングされる．

重要な点として，`batch.edge_index` はノードインデックスが再ラベル付けされたサンプリング済み部分グラフを含んでおり，そのインデックスは `0` から `batch.num_nodes - 1` の範囲になる．
`batch.edge_index` の元のノードインデックスを復元したい場合は，次のようにする．

```python
batch.n_id[batch.edge_index]
>>> tensor([[2, 3, 5, 6],
            [0, 0, 2, 3]])
```

さらに，[`NeighborLoader`](../modules/loader.html#torch_geometric.loader.NeighborLoader) はシードノード *から* サンプリングを開始する一方で，得られる部分グラフはシードノード *へ* 向かうエッジを保持する．
これは，ソースノードからデスティネーションノードへという PyG のデフォルトのメッセージパッシングの流れとよく整合している．

最後に，[`NeighborLoader`](../modules/loader.html#torch_geometric.loader.NeighborLoader) の出力のノードは，ソートされていることが保証されている．
特に，最初の `batch_size` 個のサンプリング済みノードは，サンプリングに使用されたシードノードと正確に一致する．

```python
batch.n_id[:batch.batch_size]
>>> tensor([0])
```

その後，大規模グラフ上でミニバッチ方式で GNN を学習するためのデータ読み込みルーチンとして [`NeighborLoader`](../modules/loader.html#torch_geometric.loader.NeighborLoader) を利用できる．
そのために，シンプルな2層の [`GraphSAGE`](../generated/torch_geometric.nn.models.GraphSAGE.html#torch_geometric.nn.models.GraphSAGE) モデルを作成してみよう．

```python
from torch_geometric.nn import GraphSAGE

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

model = GraphSAGE(
    in_channels=32,
    hidden_channels=64,
    out_channels=4,
    num_layers=2
).to(device)

optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
```

これで，`loader` と `model` を組み合わせて学習ルーチンを定義できる．

```python
import torch.nn.functional as F

for batch in loader:
    optimizer.zero_grad()
    batch = batch.to(device)
    out = model(batch.x, batch.edge_index)

    # NOTE Only consider predictions and labels of seed nodes:
    y = batch.y[:batch.batch_size]
    out = out[:batch.batch_size]

    loss = F.cross_entropy(out, y)
    loss.backward()
    optimizer.step()
```

この学習ループは，他の一般的な PyTorch の学習ループと同様の設計に従っている．
唯一の重要な違いは，デフォルトではモデルが `[batch.num_nodes, *]` の形状の行列を出力する一方で，我々が関心を持つのはシードノードの予測のみである点である．
そのため，ノードの予測値と正解情報 `batch.y` の両方に対して効率的なスライシングを行い，実際のシードノードの予測値と正解情報のみを取得できる．
これにより，損失およびメトリクスの計算に，最初の `batch_size` 個分のノードのみを使用することが保証される．

## Hierarchical Extension

`Neighborloader` の欠点は，ネットワークの *すべて* の深さにおいて，サンプリングされた *すべて* のノードの表現を計算してしまう点である．
しかし，後の hop でサンプリングされたノードは，後段の GNN 層におけるシードノードのノード表現にはもはや寄与しないため，無駄な計算を行っていることになる．
[`NeighborLoader`](../modules/loader.html#torch_geometric.loader.NeighborLoader) は，もはや不要なノードの埋め込みを計算しているため，わずかに遅くなる．
これは，モデルの定義を使用するデータローダーのルーチンに結びつけない，クリーンでモジュール化された，実験しやすい GNN 設計を実現するために我々が行っているトレードオフである．
[Hierarchical Neighborhood Sampling](../advanced/hgam.html) チュートリアルでは，このオーバーヘッドを排除し，ミニバッチ GNN の学習と推論をさらに高速化する方法を示している．

## Advanced Options

[`NeighborLoader`](../modules/loader.html#torch_geometric.loader.NeighborLoader) は，より高度な利用のための多くの機能を提供している．
具体的には，

- [`NeighborLoader`](../modules/loader.html#torch_geometric.loader.NeighborLoader) は，ホモジニアスグラフとヘテロジニアスグラフの両方でのサンプリングを標準でサポートしている．
  ヘテロジニアスグラフでのサンプリングを行うには，単に [`HeteroData`](../generated/torch_geometric.data.HeteroData.html#torch_geometric.data.HeteroData) オブジェクトで初期化すればよい．
  [`NeighborLoader`](../modules/loader.html#torch_geometric.loader.NeighborLoader) によるヘテロジニアスグラフでのサンプリングでは，例えばエッジタイプごとに個別にサンプリングする近傍数を指定できるなど，きめ細かなサンプリングパラメータの制御が可能である．
  詳細は [Heterogeneous Graph Learning](../advanced/heterogeneous.html) チュートリアルを参照のこと．

- デフォルトでは，[`NeighborLoader`](../modules/loader.html#torch_geometric.loader.NeighborLoader) は，異なるシードノード間でサンプリングされたノードを単一の部分グラフへ融合（fuse）する．
  これにより，シードノード間で共有される近傍が結果の部分グラフ内で重複せず，メモリを節約できる．
  この挙動は，[`NeighborLoader`](../modules/loader.html#torch_geometric.loader.NeighborLoader) に `disjoint=True` オプションを渡すことで無効化できる．

- デフォルトでは，[`NeighborLoader`](../modules/loader.html#torch_geometric.loader.NeighborLoader) から返される部分グラフは **有向（directed）** であり，これによりサンプリングする hop 数と同じ深さの GNN にしか利用できないという制約がある．
  より深い GNN を利用したい場合は，`subgraph_type` オプションを指定する．
  `"bidirectional"` に設定すると，サンプリングされたエッジは双方向エッジへ変換される．
  `"induced"` に設定すると，返される部分グラフは，サンプリングされたすべてのノードによる誘導部分グラフ（induced subgraph）となる．

- [`NeighborLoader`](../modules/loader.html#torch_geometric.loader.NeighborLoader) は，個々のシードノードからサンプリングを行うよう設計されている．
  そのため，リンク予測のシナリオには直接適用できない．
  このようなユースケースのために，我々は [`LinkNeighborLoader`](../modules/loader.html#torch_geometric.loader.LinkNeighborLoader) を開発した．これは入力エッジの集合を期待し，ソースノードとデスティネーションノードの両方から近傍サンプリングによって作成された部分グラフを返す．
