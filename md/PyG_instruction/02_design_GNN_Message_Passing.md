# Creating Message Passing Networks

- [Creating Message Passing Networks](#creating-message-passing-networks)
  - [The "MessagePassing" Base Class](#the-messagepassing-base-class)
    - [`MessagePassing(aggr="add", flow="source_to_target", node_dim=-2)`](#messagepassingaggradd-flowsource_to_target-node_dim-2)
    - [`MessagePassing.propagate(edge_index, size=None, **kwargs)`](#messagepassingpropagateedge_index-sizenone-kwargs)
    - [`MessagePassing.message(...)`](#messagepassingmessage)
    - [`MessagePassing.update(aggr_out, ...)`](#messagepassingupdateaggr_out-)
  - [GCN層の実装](#gcn層の実装)
  - [エッジ畳み込みの実装](#エッジ畳み込みの実装)

---

不規則にサイズが変化するサブグラフに対する畳み込み演算の一般化は，典型的に *neighborhood aggregation* （近傍集約） あるいは *message passing* （メッセージパッシング） 機構と表現される．
$\mathbf{x}^{(k-1)}_i \in \mathbb{R}^{F}$ は，ノード $i$ の $(k-1)$ 層目のノード特徴を表す．
$\mathbf{e}_{j,i} \in \mathbb{R}^{D}$ は，ノード $j$ からノード $i$ へのエッジ特徴を表す．
そして，*message passing graph neural network* は次のように定義される．

$$ \mathbf{x}^{(k)}_i = \gamma^{(k)} \left( \mathbf{x}^{(k-1)}_i, \bigoplus_{j \in \mathcal{N}(i)} \phi^{(k)} \left( \mathbf{x}^{(k-1)}_i, \mathbf{x}^{(k-1)}_j ,\mathbf{e}_{j,i} \right) \right) $$

ここで，$\bigoplus$ は，微分可能・置換不偏な集約関数であり，例えば，和・平均・最大値などがある．
$\gamma$ と $\phi$ は，MLP（多層パーセプトロン）のような微分可能な関数である．


## The "MessagePassing" Base Class

PyG は，[`MessagePassing`](https://pytorch-geometric.readthedocs.io/en/latest/generated/torch_geometric.nn.conv.MessagePassing.html#torch_geometric.nn.conv.MessagePassing)　基底クラスを提供しており， *message propagation* を自動的に処理することによって様々な message passing GNN の実装を助ける．
ユーザーは `message()` である $\phi$ と `update()` である $\gamma$ を定義するだけでよい．
また，集約スキームは `aggr="add"` `aggr="mean"` `aggr="max"` のいずれかを指定することができる．

以下にクラスの詳細な説明を示す．

### `MessagePassing(aggr="add", flow="source_to_target", node_dim=-2)`

集約関数として `add`（和），`mean`（平均），`max`（最大値）を指定することができる．
`flow` は，メッセージの伝播方向を指定することができ，`source_to_target`（ソースからターゲットへ）あるいは `target_to_source`（ターゲットからソースへ）を指定することができる．
`node_dim` は，どの軸に沿って伝播するかを指定できる．

### `MessagePassing.propagate(edge_index, size=None, **kwargs)`

メッセージ伝播するために最初に呼び出されるメソッドである．
エッジインデックス，メッセージ構築・ノード埋込更新に必要な全ての追加の引数を受け取る．
`propagate()` は形状 `[N, N]` のような正方隣接行列からのメッセージ変換に限られず，一般的なスパース化されたマトリクスに対しても適用可能である．
例えば，*bipartite graphs* の形状 `[N, M]` のような非正方行列に対しても，追加引数 `size=(N, M)`　によりパッシングが可能である． 
`None` が指定された場合，行列は正方行列として仮定される．

*bipartite graphs* は，ノードとエッジの集合が二つの独立した各集合がそれぞれに情報を持ち，この分割は `x=(x_N, x_M)` のようにタプルを指定することで表現でき，情報のパッシングが可能である．
*bipartite graphs* について詳細に知りたい場合は，[wikipedia](https://ja.wikipedia.org/wiki/2%E9%83%A8%E3%82%B0%E3%83%A9%E3%83%95) が分かりやすい．

### `MessagePassing.message(...)`

ノード $i$ へ， `flow="source_to_target"` ならば $(j,i) \in \mathcal{E}$ ， `flow="target_to_source"` ならば $(i,j) \in \mathcal{E}$ の各エッジから $\phi$ を通じてメッセージを構築する．
多くの引数を持つことができ，はじめに `propagate()` に渡されている．
加えて `propagate()` に渡されたテンソルは，各ノード $i$ と $j$ へ `_i` や `_j` の変数名への付加によって写像される．
例えば `x_i` と `x_j` など．
ここで一般化するために言及すると，$i$ は情報が集約される中心ノードであり，$j$ はその近傍ノードである．

### `MessagePassing.update(aggr_out, ...)`

ノード埋込を $\gamma$ によって $i \in \mathcal{V}$ を通じて更新する．
第一引数として出力用の集約関数エイリアスを `aggr_out` として受け取る．
それ以外の引数は，`propagate()` から渡された追加の引数である．

## GCN層の実装

[GCN層](https://arxiv.org/abs/1609.02907) は数学的に次のように定義される．

$$ \mathbf{x}^{(k)}_i = \sum_{j \in \mathcal{N}(i) \cup\{i\}} \dfrac{1}{\sqrt{\deg(i)}\cdot\sqrt{\deg(j)}}\cdot\left( \mathbf{W}^{\top}\cdot\mathbf{x}^{k-1}_j \right)+\mathbf{b} $$

$j \in \mathcal{N}(i) \cup\{i\}$ はノード $i$ の自己ループ（＝「自分で自分に矢印を向けている状態」のこと．近傍ノード集合にそのノード自体を含むことができる）を含む，つまり，ノード $i$ 自身とその近傍ノード $j$ の集合を表す．
近傍ノード特徴は，はじめに重み行列 $\mathbf{W}$ によって変換され，それぞれのノードの次数によって正規化され，最後に和を取る．
続いて，バイアスベクトルである $\mathbf{b}$ を集約関数の出力に適用する．
この公式は次のステップに分割される．

1. 自己ループを隣接行列に追加する．
2. ノード特徴行列 $\mathbf{x}^{k-1}_j$ を線形変換する．
3. 係数 $\mathbf{W}^{\top}$ を $\dfrac{1}{\sqrt{\deg(i)}\cdot\sqrt{\deg(j)}}$ によって正規化する．
4. $\phi$ の中でノード特徴を標準化する．
5. 近傍ノード特徴を合計する（ `aggr = "add"` を指定した場合）．
6. 最後に，バイアスベクトルを適用する．

1から3のステップは，典型的には *message passing* が実施される前に計算される． 
4から5のステップは， `MessagePassing` 基底クラスを用いて簡単に実施されます．
層の完全な実装は以下に示すようになる

```python
import torch
from torch.nn import Linear, Parameter
from torch_geometric.nn import MessagePassing
from torch_geometric.utils import add_self_loops. degree

class GCNConv(MessagePassing):
    def __init__(self, in_channels, out_channels):
        super().__init__(aggr='add') # "Add" が集約関数として設定されている．（5.と同じ設定）
        self.lin = Linear(in_channels, out_channels, bias=False)
        self.bias = Parameter(torch.empty(out_channels))

        self.reset_parameters()

    def reset_parameters(self):
        self.lin.reset_parameters()
        self.bias.data.zero_()
    
    def forward(self, x, edge_index):
        # x の形状は [N, in_channels]
        # edge_index の形状は [2, E]

        # 1. 自己ループを隣接行列に追加する．
        edge_index, _ = add_self_loops(edge_index, num_nodes=x.size(0))

        # 2. ノード特徴行列を線形変換する．
        x = self.lin(x)

        # 3. 係数によって正規化する．
        row, col = edge_index
        deg = degree(col, x.size(0), dtype=x.dtype)
        deg_inv_sqrt = deg.powo(-0.5)
        deg_inv_sqrt[deg_inv_sqrt == float('inf')] = 0
        norm = deg_inv_sqrt[row] * deg_inv_sqrt[col]

        # 4. φ の中でノード特徴を標準化する．
        # 5. 近傍ノード特徴を合計する（ `aggr = "add"` を指定した場合）．
        out = self.popagate(edge_index, x=x, norm=norm)

        # 6. 最後に，バイアスベクトルを適用する．
        out = out + self.bias

        return out
    
    def message(self, x_j, norm):
        # x_j の形状は [E, out_channels]

        # 4. φ の中でノード特徴を標準化する．
        return norm.view(-1, 1) * x_j
```

`GCNConv` は `"add"` 付きの `MessagePassing` から継承されている．
全ての層のロジックは `forward()` メソッドにより実行される．
ここで， `torch_geometric.utils.add_self_loops()` によってエッジインデックスに自己ループを加えている（1.）．
同時に， `torch.nn.Linear` インスタンスによってノード特徴量を線形変換している（2.）．

係数の標準化は，$(j,i) \in \mathcal{E}$ の各エッジのノード $i$ におけるノード次数を $\deg{(i)}$ とすると， $\frac{1}{\sqrt{\deg{(i)}}\cdot\sqrt{\deg{(j)}}}$ を計算して行う（3.） ．
その結果は， `norm` テンソルに形状 `[num_edges, ]` で保存される．

それから， `message()` ， `aggregate()` ， `update()` ，を内部的に呼び出す，`propagate()` を呼び出す．ノード $i$ のノード埋込 `x` と共に，係数標準化の `norm` は *message propagation* の付加的な引数として渡される．

`message()` メソッドは， `norm` を通して，近傍ノード特徴の `x_j` は標準化する必要がある．
ここで， `x_j` は *lifted tensor* ，つまり各ノードの近傍，各エッジの説明ノードの特徴を含んでいるテンソルである．
ノード特徴は，変数名に `_i` や `_j` が付加されることで自動的に *lifted* される．
事実，多くのテンソルは，説明・目的ノード特徴を保持する限り，このように変換される．

シンプルなメッセージ伝達層を作成するのに必要なのは、これだけです．
このレイヤーは、ディープアーキテクチャの構成要素として使用できます．
初期化して呼び出すのは次のようにやってみることです．

```python
conv = GCNConv(in_channels=16, out_channels=32)
x = conv(x, edge_index) 
```

## エッジ畳み込みの実装

エッジ畳み込み層はグラフまたは点群を処理し、数学的には次のように定義されます．

$$ \mathbf{x}^{(k)}_i = \max_{j \in \mathcal{N}(i)} h_{\Theta}\left( \mathbf{x}^{(k-1)}_i, \mathbf{x}^{(k-1)}_j - \mathbf{x}^{(k-1)}_i \right) $$

$h_{\Theta}$ は，多層パーセプトロンである．
GCNレイヤーと同様に， `MessagePassing` クラスを利用して実装が可能です．
今回は，集約関数として `max` を指定する．

```python
import torch
from torch.nn import Sequential as Seq, Linear, ReLU
from torch_geometric.nn import MessagePassing

class EdgeConv(MessagePassing):
    def __init__(self, in_channels, out_channels):
    super().__init__(aggr='max') # "Max" が集約関数として設定されている．
    self.mlp = Seq(Linear(2 * in_channels, out_channels),
                   ReLU(), 
                   Linear(out_channels, out_channels))

    def forward(self, x, edge_index):
        # x の形状は [N, in_channels]
        # edge_index の形状は [2, E]

        return self.propagate(edge_index, x=x)
    
    def message(self, x_i, x_j):
        # x_i の形状は [E, in_channels]
        # x_j の形状は [E, in_channels]

        tmp = torch.cat([x_i, x_j - x_i], dim=1) #tmp の形状は [E, 2 * in_channels]
        return self.mlp(tmp)
```

`message()` 関数内では、 `self.mlp` を使用して、各エッジ $(j,i) \in \mathcal{E}$ についてターゲットノードの特徴 `x_i` と相対的なソースノードの特徴 `x_j - x_i` の両方を変換します。

エッジ畳み込みは実際には動的畳み込みであり、特徴空間内の最近傍を使用して各層のグラフを再計算します。
幸いなことに、PyGには `torch_geometric.nn.pool.knn_graph()` というGPUアクセラレーションによるバッチ単位のk-NNグラフ生成メソッドが付属しています。

```python
from torch_geometric.nn import knn_graph

class DynamicEdgeConv(EdgeConv):
    def __init__(self, in_channels, out_channels, k=6):
        super().__init__(in_channels, out_channels)
        self.k = k

    def forward(self, x, batch=None):
        edge_index = knn_graph(x, self.k, batch, loop=False, flow=self.flow)
        return super().forward(x, edge_index)
```

ここで、`knn_graph()` は最近傍グラフを計算し、それが `EdgeConv` の `forward()` メソッドを呼び出すために使用されます。
これにより、このレイヤーの初期化と呼び出しのためのクリーンなインターフェースが実現します。

```python
conv = DynamicEdgeConv(3, 128, k=6)
x = conv(x, batch)
```