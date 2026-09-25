# Advanced Mini-Batching

- [Advanced Mini-Batching](#advanced-mini-batching)
  - [Pairs of Graphs](#pairs-of-graphs)
  - [Bipartite Graphs](#bipartite-graphs)
  - [Batching Along New Dimensions](#batching-along-new-dimensions)

---

ミニバッチ化は，深層学習モデルの学習を膨大な量のデータに対してスケールさせるうえで極めて重要である．サンプルを1つずつ処理する代わりに，ミニバッチは複数のサンプルの集合を統一された表現へとまとめ，それらを並列に効率よく処理できるようにする．画像やテキストの領域では，この処理は通常，各サンプルを同一の形状へリスケールまたはパディングし，追加の次元にまとめてグループ化することで実現される．この次元の長さは，ミニバッチにグループ化されたサンプル数に等しく，一般に `batch_size` と呼ばれる．

グラフは，*任意の* 個数のノードやエッジを保持できる最も一般的なデータ構造の一つであるため，上記2つのアプローチは実現不可能であるか，あるいは多くの不要なメモリ消費を招くことになる．PyG では，複数サンプルにわたる並列化を実現するために別のアプローチを採用している．ここでは，隣接行列を対角方向に積み重ねることで（複数の孤立したサブグラフを保持する巨大なグラフを作り），ノード特徴量とターゲット特徴量は単純にノード次元方向へ連結される．すなわち，

$$\begin{split}\mathbf{A} = \begin{bmatrix} \mathbf{A}_1 & & \\ & \ddots & \\ & & \mathbf{A}_n \end{bmatrix}, \qquad \mathbf{X} = \begin{bmatrix} \mathbf{X}_1 \\ \vdots \\ \mathbf{X}_n \end{bmatrix}, \qquad \mathbf{Y} = \begin{bmatrix} \mathbf{Y}_1 \\ \vdots \\ \mathbf{Y}_n \end{bmatrix}.\end{split}$$

この手続きには，他のバッチ化手続きに対する重要な利点がいくつかある．

1. メッセージパッシング方式に基づく GNN 演算子は，異なるグラフに属する2つのノード間でメッセージが交換されることは依然としてないため，変更を加える必要がない．
2. 計算量やメモリ使用量のオーバーヘッドが生じない．例えば，このバッチ化手続きは，ノードやエッジの特徴量に対するパディングを一切行うことなく機能する．なお，隣接行列については非ゼロ要素（すなわちエッジ）のみを保持するスパースな形式で保存されるため，追加のメモリオーバーヘッドは生じない点に注意されたい．

PyG は，[`torch_geometric.loader.DataLoader`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/modules/loader.html#torch_geometric.loader.DataLoader) クラスを用いることで，複数のグラフを単一の巨大なグラフへ自動的にバッチ化する．内部的には，`DataLoader` は通常の PyTorch の [`torch.utils.data.DataLoader`](https://docs.pytorch.org/docs/main/data.html#torch.utils.data.DataLoader) にすぎず，その `collate()` の機能，すなわちサンプルのリストをどのようにグループ化するかという定義を上書きしたものである．したがって，PyTorch の [`DataLoader`](https://docs.pytorch.org/docs/main/data.html#torch.utils.data.DataLoader) に渡すことができる全ての引数は，PyG の [`DataLoader`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/modules/loader.html#torch_geometric.loader.DataLoader) にも渡すことができる．例えば，ワーカー数を指定する `num_workers` などである．

最も一般的な形式では，PyG の [`DataLoader`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/modules/loader.html#torch_geometric.loader.DataLoader) は，現在処理中のグラフより前に収集された全グラフの累積ノード数だけ `edge_index` テンソルを自動的にインクリメントし，`edge_index` テンソル（形状 `[2, num_edges]`）を2番目の次元で連結する．これは，メッシュにおける面インデックスである `face` テンソルについても同様である．それ以外の全てのテンソルは，値をそれ以上インクリメントされることなく，単純に第1次元で連結される．

しかし，（以下で説明するように）ユーザーがこの挙動を自分のニーズに合わせて積極的に変更したいという，いくつかの特殊なユースケースが存在する．PyG では，[`torch_geometric.data.Data.__inc__()`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.Data.html#torch_geometric.data.Data.__inc__) と [`torch_geometric.data.Data.__cat_dim__()`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.Data.html#torch_geometric.data.Data.__cat_dim__) の機能を上書きすることで，基盤となるバッチ化手続きを変更できる．変更を加えない場合，これらは [`Data`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.Data.html#torch_geometric.data.Data) クラス内で次のように定義されている．

```python
def __inc__(self, key, value, *args, **kwargs):
    if 'index' in key:
        return self.num_nodes
    else:
        return 0

def __cat_dim__(self, key, value, *args, **kwargs):
    if 'index' in key:
        return 1
    else:
        return 0
```

[`__inc__()`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.Data.html#torch_geometric.data.Data.__inc__) は，2つの連続するグラフ属性間のインクリメント量を定義していることが分かる．PyG はデフォルトで，属性名に（歴史的な理由により）部分文字列 `index` が含まれる場合，その属性をノード数だけインクリメントする．これは `edge_index` や `node_index` のような属性にとって都合が良い．ただし，属性名に部分文字列 `index` が含まれていても，本来インクリメントされるべきではない属性については，予期しない挙動を招く可能性がある点に注意されたい．そのため，バッチ化の出力を常に二重チェックすることがベストプラクティスである．さらに，[`__cat_dim__()`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.Data.html#torch_geometric.data.Data.__cat_dim__) は，同一属性のグラフテンソルをどの次元で連結すべきかを定義する．これら2つの関数はいずれも，[`Data`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.Data.html#torch_geometric.data.Data) クラスに格納された各属性に対して呼び出され，それぞれの `key` と値 `item` が引数として渡される．

以下では，[`__inc__()`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.Data.html#torch_geometric.data.Data.__inc__) と [`__cat_dim__()`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.Data.html#torch_geometric.data.Data.__cat_dim__) の変更がどうしても必要となるいくつかのユースケースを紹介する．

## Pairs of Graphs

例えばグラフマッチングのようなアプリケーション向けに，複数のグラフを単一の [`Data`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.Data.html#torch_geometric.data.Data) オブジェクトに格納したい場合，それら全てのグラフにわたって正しいバッチ化の挙動を確保する必要がある．例えば，ソースグラフ $\mathcal{G}_s$ とターゲットグラフ $\mathcal{G}_t$ の2つのグラフを1つの [`Data`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.Data.html#torch_geometric.data.Data) に格納する場合を考えてみよう．

```python
from torch_geometric.data import Data

class PairData(Data):
    pass

data = PairData(x_s=x_s, edge_index_s=edge_index_s,  # Source graph.
                x_t=x_t, edge_index_t=edge_index_t)  # Target graph.
```

この場合，`edge_index_s` はソースグラフ $\mathcal{G}_s$ のノード数（例えば `x_s.size(0)`）だけ増加させ，`edge_index_t` はターゲットグラフ $\mathcal{G}_t$ のノード数（例えば `x_t.size(0)`）だけ増加させる必要がある．

```python
class PairData(Data):
    def __inc__(self, key, value, *args, **kwargs):
        if key == 'edge_index_s':
            return self.x_s.size(0)
        if key == 'edge_index_t':
            return self.x_t.size(0)
        return super().__inc__(key, value, *args, **kwargs)
```

簡単なテストスクリプトを用意することで，この `PairData` のバッチ化挙動を検証できる．

```python
from torch_geometric.loader import DataLoader

 x_s = torch.randn(5, 16)  # 5 nodes.
 edge_index_s = torch.tensor([
     [0, 0, 0, 0],
     [1, 2, 3, 4],
 ])

 x_t = torch.randn(4, 16)  # 4 nodes.
 edge_index_t = torch.tensor([
     [0, 0, 0],
     [1, 2, 3],
 ])

 data = PairData(x_s=x_s, edge_index_s=edge_index_s,
                 x_t=x_t, edge_index_t=edge_index_t)

 data_list = [data, data]
 loader = DataLoader(data_list, batch_size=2)
 batch = next(iter(loader))

 print(batch)
 >>> PairDataBatch(x_s=[10, 16], edge_index_s=[2, 8],
                   x_t=[8, 16], edge_index_t=[2, 6])

 print(batch.edge_index_s)
 >>> tensor([[0, 0, 0, 0, 5, 5, 5, 5],
             [1, 2, 3, 4, 6, 7, 8, 9]])

 print(batch.edge_index_t)
 >>> tensor([[0, 0, 0, 4, 4, 4],
             [1, 2, 3, 5, 6, 7]])
```

ここまでは順調である！ $\mathcal{G}_s$ と $\mathcal{G}_t$ のノード数が異なっていても，`edge_index_s` と `edge_index_t` は正しくバッチ化されている．しかし，PyG が `PairData` オブジェクトの中から実際のグラフを識別できないため，各ノードをそれぞれのグラフへ対応付ける `batch` 属性が欠落している．そこで登場するのが，[`DataLoader`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/modules/loader.html#torch_geometric.loader.DataLoader) の `follow_batch` 引数である．これを用いることで，どの属性についてバッチ情報を維持したいかを指定できる．

```python
loader = DataLoader(data_list, batch_size=2, follow_batch=['x_s', 'x_t'])
batch = next(iter(loader))

print(batch)
>>> PairDataBatch(x_s=[10, 16], edge_index_s=[2, 8], x_s_batch=[10],
                  x_t=[8, 16], edge_index_t=[2, 6], x_t_batch=[8])

print(batch.x_s_batch)
>>> tensor([0, 0, 0, 0, 0, 1, 1, 1, 1, 1])

print(batch.x_t_batch)
>>> tensor([0, 0, 0, 0, 1, 1, 1, 1])
```

このように，`follow_batch=['x_s', 'x_t']` を指定することで，ノード特徴量 `x_s` と `x_t` それぞれに対応する割り当てベクトル `x_s_batch` と `x_t_batch` が正しく生成される．この情報を用いることで，単一の `Batch` オブジェクトに含まれる複数のグラフに対して，例えばグローバルプーリングのような縮約操作を実行できるようになる．

## Bipartite Graphs

二部グラフの隣接行列は，2種類の異なるノード型に属するノード間の関係を定義する．一般に，それぞれのノード型のノード数は一致している必要がなく，その結果，形状 $\mathbf{A} \in \{ 0, 1 \}^{N \times M}$（$N \neq M$ となりうる）の非正方な隣接行列となる．二部グラフのミニバッチ化手続きでは，`edge_index` 内のエッジのソースノードは，同じく `edge_index` 内のエッジのターゲットノードとは異なる方法でインクリメントされる必要がある．これを実現するために，それぞれ対応するノード特徴量 `x_s` と `x_t` を持つ，2つのノード型間の二部グラフを考える．

```python
from torch_geometric.data import Data

class BipartiteData(Data):
    pass

data = BipartiteData(x_s=x_s, x_t=x_t, edge_index=edge_index)
```

二部グラフにおいて正しいミニバッチ化手続きを行うためには，`edge_index` 内のエッジのソースノードとターゲットノードをそれぞれ独立にインクリメントするよう，PyG に伝える必要がある．

```python
class BipartiteData(Data):
    def __inc__(self, key, value, *args, **kwargs):
        if key == 'edge_index':
            return torch.tensor([[self.x_s.size(0)], [self.x_t.size(0)]])
        return super().__inc__(key, value, *args, **kwargs)
```

ここでは，`edge_index[0]`（エッジのソースノード）が `x_s.size(0)` だけインクリメントされ，`edge_index[1]`（エッジのターゲットノード）が `x_t.size(0)` だけインクリメントされる．簡単なテストスクリプトを実行することで，この実装を再び検証できる．

```python
from torch_geometric.loader import DataLoader

x_s = torch.randn(2, 16)  # 2 nodes.
x_t = torch.randn(3, 16)  # 3 nodes.
edge_index = torch.tensor([
    [0, 0, 1, 1],
    [0, 1, 1, 2],
])

data = BipartiteData(x_s=x_s, x_t=x_t, edge_index=edge_index)

data_list = [data, data]
loader = DataLoader(data_list, batch_size=2)
batch = next(iter(loader))

print(batch)
>>> BipartiteDataBatch(x_s=[4, 16], x_t=[6, 16], edge_index=[2, 8])

print(batch.edge_index)
>>> tensor([[0, 0, 1, 1, 2, 2, 3, 3],
            [0, 1, 1, 2, 3, 4, 4, 5]])
```

これもまた，まさに我々が意図した通りの挙動である！

## Batching Along New Dimensions

（グラフレベルの属性やターゲットなどのように）`data` オブジェクトの属性を，（古典的なミニバッチ化のように）新たなバッチ次元を獲得する形でバッチ化したい場合もある．具体的には，形状 `[num_features]` を持つ属性のリストは，`[num_examples * num_features]` ではなく `[num_examples, num_features]` として返されるべきである．PyG は，[`__cat_dim__()`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.Data.html#torch_geometric.data.Data.__cat_dim__) の連結次元として [`None`](https://docs.python.org/3/library/constants.html#None) を返すことで，これを実現している．

```python
from torch_geometric.data import Data
from torch_geometric.loader import DataLoader

class MyData(Data):
    def __cat_dim__(self, key, value, *args, **kwargs):
        if key == 'foo':
            return None
        return super().__cat_dim__(key, value, *args, **kwargs)

edge_index = torch.tensor([
   [0, 1, 1, 2],
   [1, 0, 2, 1],
])
foo = torch.randn(16)

data = MyData(num_nodes=3, edge_index=edge_index, foo=foo)

data_list = [data, data]
loader = DataLoader(data_list, batch_size=2)
batch = next(iter(loader))

print(batch)
>>> MyDataBatch(num_nodes=6, edge_index=[2, 8], foo=[2, 16])
```

望み通り，`batch.foo` はバッチ次元と特徴次元という2つの次元で表現されるようになった．
