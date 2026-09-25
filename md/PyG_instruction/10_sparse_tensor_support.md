# Memory-Efficient Aggregations

- [Memory-Efficient Aggregations](#memory-efficient-aggregations)

---

PyG の [MessagePassing](../generated/torch_geometric.nn.conv.MessagePassing.html#torch_geometric.nn.conv.MessagePassing) インターフェースは，近傍ノードからのメッセージを集約するために gather-scatter 方式を採用している．
例えば，次のようなメッセージパッシング層を考える．

$$\mathbf{x}^{\prime}_i = \sum_{j \in \mathcal{N}(i)} \textrm{MLP}(\mathbf{x}_j - \mathbf{x}_i),$$

これは，次のように実装できる．

```python
from torch_geometric.nn import MessagePassing

x = ...           # Node features of shape [num_nodes, num_features]
edge_index = ...  # Edge indices of shape [2, num_edges]

class MyConv(MessagePassing):
    def __init__(self):
        super().__init__(aggr="add")

    def forward(self, x, edge_index):
        return self.propagate(edge_index, x=x)

    def message(self, x_i, x_j):
        return MLP(x_j - x_i)
```

内部的には，[MessagePassing](../generated/torch_geometric.nn.conv.MessagePassing.html#torch_geometric.nn.conv.MessagePassing) の実装は，次のようなコードを生成する．

```python
from torch_geometric.utils import scatter

x = ...           # Node features of shape [num_nodes, num_features]
edge_index = ...  # Edge indices of shape [2, num_edges]

x_j = x[edge_index[0]]  # Source node features [num_edges, num_features]
x_i = x[edge_index[1]]  # Target node features [num_edges, num_features]

msg = MLP(x_j - x_i)  # Compute message for each edge

# Aggregate messages based on target node indices
out = scatter(msg, edge_index[1], dim=0, dim_size=x.size(0), reduce='sum')
```

gather-scatter による定式化は多くの有用な GNN 実装に一般化できる一方で，`x_j` と `x_i` を明示的に実体化（materialize）する必要があるという欠点があり，大規模で密なグラフにおいては高いメモリ消費量につながる．

幸い，すべての GNN が `x_j` や `x_i` を明示的に実体化する形で実装される必要があるわけではない．
場合によっては，GNN を単純なスパース行列積として実装することもできる．
経験則として，これはメッセージを計算する際に中心ノードの特徴量 `x_i` や多次元のエッジ特徴量を利用しない GNN に当てはまる．
例えば，[GINConv](../generated/torch_geometric.nn.conv.GINConv.html#torch_geometric.nn.conv.GINConv) 層

$$\mathbf{x}^{\prime}_i = \textrm{MLP} \left( (1 + \epsilon) \cdot \mathbf{x}_i + \sum_{j \in \mathcal{N}(i)} \mathbf{x}_j \right),$$

は，次を計算することと等価である．

$$\mathbf{X}^{\prime} = \textrm{MLP} \left( (1 + \epsilon) \cdot \mathbf{X} + \mathbf{A}\mathbf{X} \right),$$

ここで，$\mathbf{A}$ は形状 `[num_nodes, num_nodes]` のスパース隣接行列を表す．この定式化により，専用の高速なスパース行列積の実装を活用できるようになる．

**PyG >= 1.6.0** では，スパース行列積による GNN のサポートが正式に強化され，**メモリ消費量の削減**と**実行速度の向上**が実現されている．
その成果として，`torch_sparse` パッケージ由来の `SparseTensor` クラスを導入した．このクラスは，[“Design Principles for Sparse Matrix Multiplication on the GPU”](https://arxiv.org/abs/1803.08601) 論文に基づく，高速なスパース行列積の forward/backward パスを実装している．

`SparseTensor` クラスの利用方法は直感的であり，`scipy` がスパース行列を扱う方法と似ている．

```python
from torch_sparse import SparseTensor

adj = SparseTensor(row=edge_index[0], col=edge_index[1], value=...,
                   sparse_sizes=(num_nodes, num_nodes))
# value is optional and can be None

# Obtain different representations (COO, CSR, CSC):
row,    col, value = adj.coo()
rowptr, col, value = adj.csr()
colptr, row, value = adj.csc()

adj = adj[:100, :100]  # Slicing, indexing and masking support
adj = adj.set_diag()   # Add diagonal entries
adj_t = adj.t()        # Transpose
out = adj.matmul(x)    # Sparse-dense matrix multiplication
adj = adj.matmul(adj)  # Sparse-sparse matrix multiplication

# Creating SparseTensor instances:
adj = SparseTensor.from_dense(mat)
adj = SparseTensor.eye(100, 100)
adj = SparseTensor.from_scipy(mat)
```

我々の [MessagePassing](../generated/torch_geometric.nn.conv.MessagePassing.html#torch_geometric.nn.conv.MessagePassing) インターフェースは，メッセージを伝播する際の入力として [torch.Tensor](https://docs.pytorch.org/docs/main/tensors.html#torch.Tensor) と `SparseTensor` の両方を扱うことができる．
ただし，有向グラフを `SparseTensor` として保持する場合，`propagate()` には**転置したスパース行列**を入力するよう注意する必要がある．

```python
conv = GCNConv(16, 32)
out1 = conv(x, edge_index)
out2 = conv(x, adj.t())
assert torch.allclose(out1, out2)

conv = GINConv(nn=Sequential(Linear(16, 32), ReLU(), Linear(32, 32)))
out1 = conv(x, edge_index)
out2 = conv(x, adj.t())
assert torch.allclose(out1, out2)
```

スパース行列積を活用するために，[MessagePassing](../generated/torch_geometric.nn.conv.MessagePassing.html#torch_geometric.nn.conv.MessagePassing) インターフェースは `message_and_aggregate()` 関数（`message()` と `aggregate()` の2つの関数を1つの計算ステップに融合したもの）を導入している．この関数は，実装されている場合に呼び出され，`edge_index` の入力として `SparseTensor` を受け取る．
これを用いると，[GINConv](../generated/torch_geometric.nn.conv.GINConv.html#torch_geometric.nn.conv.GINConv) 層は次のように実装できる．

```python
import torch_sparse

class GINConv(MessagePassing):
    def __init__(self):
        super().__init__(aggr="add")

    def forward(self, x, edge_index):
        out = self.propagate(edge_index, x=x)
        return MLP((1 + eps) x + out)

    def message(self, x_j):
        return x_j

    def message_and_aggregate(self, adj_t, x):
        return torch_sparse.matmul(adj_t, x, reduce=self.aggr)
```

新しい `SparseTensor` 形式を試してみるのは簡単である．我々のすべての GNN は，追加の変更なしにこの形式にそのまま対応しているためである．
`edge_index` 形式から新たに導入された `SparseTensor` 形式へ変換するには，[torch_geometric.transforms.ToSparseTensor](../generated/torch_geometric.transforms.ToSparseTensor.html#torch_geometric.transforms.ToSparseTensor) 変換を利用すればよい．

```python
import torch
import torch.nn.functional as F

from torch_geometric.nn import GCNConv
import torch_geometric.transforms as T
from torch_geometric.datasets import Planetoid

dataset = Planetoid("Planetoid", name="Cora", transform=T.ToSparseTensor())
data = dataset[0]
>>> Data(adj_t=[2708, 2708, nnz=10556], x=[2708, 1433], y=[2708], ...)

class GNN(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1 = GCNConv(dataset.num_features, 16, cached=True)
        self.conv2 = GCNConv(16, dataset.num_classes, cached=True)

    def forward(self, x, adj_t):
        x = self.conv1(x, adj_t)
        x = F.relu(x)
        x = self.conv2(x, adj_t)
        return F.log_softmax(x, dim=1)

model = GNN()
optimizer = torch.optim.Adam(model.parameters(), lr=0.01)

def train(data):
    model.train()
    optimizer.zero_grad()
    out = model(data.x, data.adj_t)
    loss = F.nll_loss(out, data.y)
    loss.backward()
    optimizer.step()
    return float(loss)

for epoch in range(1, 201):
    loss = train(data)
```

`T.ToSparseTensor()` によるデータ変換の部分を除けば，コードは従来と全く同じままである．
さらなる利点として，`SparseTensor` クラスを利用した [MessagePassing](../generated/torch_geometric.nn.conv.MessagePassing.html#torch_geometric.nn.conv.MessagePassing) の実装は，集約処理がもはやアトミック演算に依存しないため，GPU 上で決定的（deterministic）になる．

なお，GNN がメッセージパッシングの定式化に単次元または多次元のエッジ情報（それぞれ `edge_weight` または `edge_attr`）を組み込む場合，GNN 層の実行方法がわずかに変化する点に注意が必要である．
具体的には，これらの属性は `SparseTensor` オブジェクトの値として直接追加されることが期待される．
GNN を次のように呼び出す代わりに，

```python
conv = GMMConv(16, 32, dim=3)
out = conv(x, edge_index, edge_attr)
```

次のように GNN 演算子を実行する．

```python
conv = GMMConv(16, 32, dim=3)
adj = SparseTensor(row=edge_index[0], col=edge_index[1], value=edge_attr)
out = conv(x, adj.t())
```

> **Note**
>
> この機能はまだ実験的であるため，一部の操作（例えばグラフプーリング手法など）では，依然として `edge_index` 形式の入力が必要となる場合がある．`adj_t` を `(edge_index, edge_attr)` に戻すには，次のようにすればよい．

```python
row, col, edge_attr = adj_t.t().coo()
edge_index = torch.stack([row, col], dim=0)
```

`SparseTensor` についてどう思うか，どのように改善できるか，また予期しない挙動に遭遇した場合は，ぜひ教えてほしい．
