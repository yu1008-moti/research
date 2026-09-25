# Hierarchical Neighborhood Sampling

- [Hierarchical Neighborhood Sampling](#hierarchical-neighborhood-sampling)
  - [Usage](#usage)
  - [Examples](#examples)

---

PyG の設計原則の一つは，モデルとデータ読み込みルーチンが交換可能であるべきだということであり，これにより柔軟な GNN とデータ読み込みの実験が可能になる．
そのため，モデルは通常，フルバッチ学習とミニバッチ学習のいずれの戦略を適用するかに関わらず，データ読み込みに依存しない形で記述できる．例えば，[`DataLoader`](../modules/loader.html#torch_geometric.loader.DataLoader)，[`NeighborLoader`](../modules/loader.html#torch_geometric.loader.NeighborLoader)，[`ClusterLoader`](../modules/loader.html#torch_geometric.loader.ClusterLoader) などを介して．
しかし，一部のシナリオでは，この柔軟性は性能の犠牲の上に成り立っており，モデルが基盤となるデータ読み込みルーチンの特殊な性質を活用できないためである．
そのような制約の一つとして，[`NeighborLoader`](../modules/loader.html#torch_geometric.loader.NeighborLoader) ルーチンで学習された GNN は，ネットワークの全ての深さにおいて全ノードの表現を反復的に構築するが，後の hop でサンプリングされたノードは，それ以降の GNN 層でシードノードのノード表現に寄与しなくなるため，無駄な計算を行ってしまうという点が挙げられる．

*Hierarchical Neighborhood Sampling*（階層的近傍サンプリング）または *Hierarchical Graph Adjacency Matrix (HGAM)* は，PyG で利用可能な，このオーバーヘッドを排除し，ミニバッチ GNN の学習と推論を高速化する技術である．
その主なアイデアは，各 GNN 層への入力前に，返された部分グラフの隣接行列を段階的にトリミング（縮小）することである．
これは複数のモデルにわたってシームレスに機能し，基本的に，与えられたミニバッチのシードノードの表現を生成するために必要な計算量を削減する．

重要な点として，HGAM は最終的なノード表現の計算が（バッチ計算の本来の対象である）シードノードに対してのみ必要であることを認識している．
これにより，HGAM は GNN の各層が，その層で必要となるノードの表現のみを計算できるようにし，考慮している GNN の深さが増すほど大きくなる形で，計算量の削減と学習プロセスの高速化を実現する．
実際には，これは GNN 層を通じて計算が進むにつれて，**隣接行列（trimming the adjacency matrix）**と各種の**特徴行列（features matrices）**をトリミングすることによって達成される．
これは，（サンプリング手法によってミニバッチが構築された元となる）シード／ターゲットノードの表現を計算するために，GNN の層を進むにつれて関連する近傍の深さが縮小していくという事実と整合している．
HGAM によるトリミングが可能なのは，サンプリングによって構築された部分グラフのノードが *Breadth First Search (BFS)*（幅優先探索）戦略に従って順序付けられているためであり，これは隣接行列の行と列が，シードノード（任意の順序）から始まり，最初のシードノードの1-hop近傍，続いて2番目のシードノードの1-hopサンプリング近傍，という順で続くノード順序を参照することを意味する．
ミニバッチ内のノードの BFS 順序付けにより，部分グラフの隣接行列を段階的にトリミング（縮小）することが可能になる．
この段階的なトリミングは，BFS 順序付けのおかげで計算上都合よく行うことができ，これはシードノードから遠いノードほど，順序付けられたノードのリストの中でより遠くに現れるためである．

このトリミングをサポートし，効果的に実装するために，PyG および pyg-lib における [`NeighborLoader`](../modules/loader.html#torch_geometric.loader.NeighborLoader) の実装は，各 hop でサンプリングされたノード数とエッジ数を追加で返すようになっている．
この情報により，隣接行列を高速に操作することが可能になり，それが大幅な計算量の削減につながる．
[`NeighborLoader`](../modules/loader.html#torch_geometric.loader.NeighborLoader) は，専用の属性 `num_sampled_nodes` と `num_sampled_edges` を介してこのメタデータを準備する．
これは，ホモジニアスグラフ・ヘテロジニアスグラフの両方について返される [`Batch`](../generated/torch_geometric.data.Batch.html#torch_geometric.data.Batch) オブジェクトからアクセスできる．

まとめると，HGAM は [`NeighborLoader`](../modules/loader.html#torch_geometric.loader.NeighborLoader) のシナリオにおいて効率的なメッセージパッシング計算を可能にする特殊なデータ構造である．
HGAM は PyG に実装されており，専用の [`trim_to_layer()`](../modules/utils.html#torch_geometric.utils.trim_to_layer) 機能を介して利用できる．
HGAM は現在，PyG ユーザーが自由にオン・オフを切り替えられるオプションである（現在のデフォルトはオフ）．

## Usage

ここでは，[`NeighborLoader`](../modules/loader.html#torch_geometric.loader.NeighborLoader) と組み合わせて HGAM 機能を利用する方法の例を示す．

- **ホモジニアスデータの例：**

```python
from torch_geometric.datasets import Planetoid
from torch_geometric.loader import NeighborLoader

data = Planetoid(path, name='Cora')[0]

loader = NeighborLoader(
    data,
    num_neighbors=[10] * 3,
    batch_size=128,
)

batch = next(iter(loader))
print(batch)
>>> Data(x=[1883, 1433], edge_index=[2, 5441], y=[1883], train_mask=[1883],
         val_mask=[1883], test_mask=[1883], batch_size=128,
         num_sampled_nodes=[4], num_sampled_edges=[3])

print(batch.num_sampled_nodes)
>>> [128, 425, 702, 628]  # Number of sampled nodes per hop/layer.
print(batch.num_sampled_edges)
>>> [520, 2036, 2885]  # Number of sampled edges per hop/layer.
```

- **ヘテロジニアスデータの例：**

```python
from torch_geometric.datasets import OGB_MAG
from torch_geometric.loader import NeighborLoader

data = OGB_MAG(path)[0]

loader = NeighborLoader(
    data,
    num_neighbors=[10] * 3,
    batch_size=128,
    input_nodes='paper',
)

batch = next(iter(loader))
print(batch)
>>> HeteroData(
    paper={
        x=[2275, 128],
        num_sampled_nodes=[3],
        batch_size=128,
    },
    author={
        num_nodes=2541,
        num_sampled_nodes=[3],
    },
    institution={
        num_nodes=0,
        num_sampled_nodes=[3],
    },
    field_of_study={
        num_nodes=0,
        num_sampled_nodes=[3],
    },
    (author, affiliated_with, institution)={
        edge_index=[2, 0],
        num_sampled_edges=[2],
    },
    (author, writes, paper)={
        edge_index=[2, 3255],
        num_sampled_edges=[2],
    },
    (paper, cites, paper)={
        edge_index=[2, 2691],
        num_sampled_edges=[2],
    },
    (paper, has_topic, field_of_study)={
        edge_index=[2, 0],
        num_sampled_edges=[2],
    }
    )
print(batch['paper'].num_sampled_nodes)
>>> [128, 508, 1598]  # Number of sampled paper nodes per hop/layer.

print(batch['author', 'writes', 'paper'].num_sampled_edges)
>>>> [629, 2621]  # Number of sampled author<>paper edges per hop/layer.
```

属性 `num_sampled_nodes` と `num_sampled_edges` は，GNN 内部で [`trim_to_layer()`](../modules/utils.html#torch_geometric.utils.trim_to_layer) 関数によって次のように利用できる．

```python
from torch_geometric.datasets import Reddit
from torch_geometric.loader import NeighborLoader
from torch_geometric.nn import SAGEConv
from torch_geometric.utils import trim_to_layer

dataset = Reddit(path)
loader = NeighborLoader(data, num_neighbors=[10, 5, 5], ...)

class GNN(torch.nn.Module):
    def __init__(self, in_channels: int, out_channels: int, num_layers: int):
        super().__init__()

        self.convs = ModuleList([SAGEConv(in_channels, 64)])
        for _ in range(num_layers - 1):
            self.convs.append(SAGEConv(hidden_channels, hidden_channels))
        self.lin = Linear(hidden_channels, out_channels)

    def forward(
        self,
        x: Tensor,
        edge_index: Tensor,
        num_sampled_nodes_per_hop: List[int],
        num_sampled_edges_per_hop: List[int],
    ) -> Tensor:

        for i, conv in enumerate(self.convs):
            # Trim edge and node information to the current layer `i`.
            x, edge_index, _ = trim_to_layer(
                i, num_sampled_nodes_per_hop, num_sampled_edges_per_hop,
                x, edge_index)

            x = conv(x, edge_index).relu()

        return self.lin(x)
```

## Examples

PyG の `examples/` フォルダには，HGAM の完全な例が用意されている．

- `examples/hierarchical_sampling.py`：HGAM の基本的な使用方法を示す [example](https://github.com/pyg-team/pytorch_geometric/blob/master/examples/hierarchical_sampling.py)．
- `examples/hetero/hierarchical_sage.py`：ヘテロジニアスグラフにおける HGAM の [example](https://github.com/pyg-team/pytorch_geometric/blob/master/examples/hetero/hierarchical_sage.py)．
