# Heterogeneous Graph Learning

- [Heterogeneous Graph Learning](#heterogeneous-graph-learning)
  - [Example Graph](#example-graph)
  - [Creating Heterogeneous Graphs](#creating-heterogeneous-graphs)
    - [便利な関数群](#便利な関数群)
  - [ヘテロジニアスグラフの変換](#ヘテロジニアスグラフの変換)
  - [ヘテロジニアスGNNの作成](#ヘテロジニアスgnnの作成)
    - [GNNモデルの自動変換](#gnnモデルの自動変換)
    - [Heterogeneous Convolution Wrapper の利用](#heterogeneous-convolution-wrapper-の利用)
    - [既存のヘテロジニアス演算子を利用する](#既存のヘテロジニアス演算子を利用する)
  - [ヘテロジニアスグラフのサンプラー](#ヘテロジニアスグラフのサンプラー)

---

実世界のデータセットは，しばしば *heterogeneous graphs*（ヘテロジニアスグラフ）として表現される．
これは，複数の種類のノード・エッジを保持するグラフのことであり，例えばソーシャルネットワークのようなレコメンデーションシステムで頻繁に見られる．

ヘテロジニアスグラフは，構造的な観点からホモジニアス（単一種類）なグラフとは異なる．
ノードとエッジがそれぞれ異なる型を持ち，型ごとに異なる次元数を持ちうるため，単一の特徴テンソルではなく，型ごとに独立した特徴テンソルとして表現する必要がある．
さらに，メッセージパッシングの定式化自体も，ノードやエッジの型に応じて処理を条件分岐させる必要がある．

## Example Graph

具体例として，OGB（Open Graph Benchmark）が提供する学術ネットワークデータセット `ogbn-mag` を用いる．

このネットワークは，1,939,743 個のノードを持ち，これらは次の4種類に分類される．

- `author`（著者）
- `paper`（論文）
- `institution`（研究機関）
- `field_of_study`（研究分野）

エッジは 21,111,007 本存在し，次の4種類に分類される．

- `writes`（著者 → 論文）
- `affiliated_with`（著者 → 研究機関）
- `cites`（論文 → 論文）
- `has_topic`（論文 → 研究分野）

このデータセットにおける学習タスクは，グラフ情報を用いて各論文が発表された媒体（学会またはジャーナル）を予測することである．

## Creating Heterogeneous Graphs

PyG は，このようなヘテロジニアスグラフを表現するために [`HeteroData`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.HeteroData.html) クラスを提供している．

ノードの型は単一の文字列キーで識別され，エッジの型は `(source_type, edge_type, destination_type)` という3つ組（トリプレット）で識別される．
これにより，型ごとに異なる特徴次元を持つことが許容される．

```python
from torch_geometric.data import HeteroData

data = HeteroData()

data['paper'].x = ... # [num_papers, num_features_paper]
data['author'].x = ... # [num_authors, num_features_author]
data['institution'].x = ... # [num_institutions, num_features_institution]
data['field_of_study'].x = ... # [num_field, num_features_field]

data['paper', 'cites', 'paper'].edge_index = ... # [2, num_edges_cites]
data['author', 'writes', 'paper'].edge_index = ... # [2, num_edges_writes]
data['author', 'affiliated_with', 'institution'].edge_index = ... # [2, num_edges_affiliated]
data['paper', 'has_topic', 'field_of_study'].edge_index = ... # [2, num_edges_topic]

data['paper', 'cites', 'paper'].edge_attr = ... # [num_edges_cites, num_features_cites]
data['author', 'writes', 'paper'].edge_attr = ... # [num_edges_writes, num_features_writes]
data['author', 'affiliated_with', 'institution'].edge_attr = ... # [num_edges_affiliated, num_features_affiliated]
data['paper', 'has_topic', 'field_of_study'].edge_attr = ... # [num_edges_topic, num_features_topic]
```

ノード・エッジの特徴テンソルは，はじめてアクセスされたタイミングで自動的に初期化される．
`data.x_dict` や `data.edge_index_dict` のように `data.{属性名}_dict` という形式でアクセスすると，型をキーとした辞書が得られる．これは，GNN モデルへの入力としてそのまま利用できる非常に便利な形式である．

```python
model = HeteroGNN(...)

output = model(data.x_dict, data.edge_index_dict, data.edge_attr_dict)
```

PyG が既に提供しているデータセットであれば，直接インポートするだけで自動的にダウンロード・前処理が行われる．

```python
from torch_geometric.datasets import OGB_MAG

dataset = OGB_MAG(root='./data', preprocess='metapath2vec')
data = dataset[0]
```

```python
HeteroData(
  paper={
    x=[736389, 128],
    y=[736389],
    train_mask=[736389],
    val_mask=[736389],
    test_mask=[736389]
  },
  author={ x=[1134649, 128] },
  institution={ x=[8740, 128] },
  field_of_study={ x=[59965, 128] },
  (author, affiliated_with, institution)={ edge_index=[2, 1043998] },
  (author, writes, paper)={ edge_index=[2, 7145660] },
  (paper, cites, paper)={ edge_index=[2, 5416271] },
  (paper, has_topic, field_of_study)={ edge_index=[2, 7505078] }
)
```

なお，`ogbn-mag` は本来 `paper`（論文）ノードにしか特徴量を持たない．
しかし，PyG が提供する `OGB_MAG` データセットには `preprocess` オプションがあり，`"metapath2vec"` または `"TransE"` を指定することで，元々特徴量を持たない他のノード型（`author`，`institution`，`field_of_study`）に対しても構造的な特徴量を生成できる．
これは，OGB のリーダーボード上位の投稿でも採用されている一般的な手法に従ったものである．

### 便利な関数群

`HeteroData` の各ノード・エッジストアは，個別にインデックスアクセスすることができる．

```python
paper_node_data = data['paper']
cites_edge_data = data['paper', 'cites', 'paper']
```

エッジ型については，ノード型の組み合わせやエッジ型名だけで一意に識別できる場合，省略した書き方でもアクセスできる．

```python
cites_edge_data = data['paper', 'paper']
cites_edge_data = data['cites']
```

既存のノード型に新しい属性を追加したり，ノード型・エッジ型そのものを削除したりすることも可能である．

```python
data['paper'].year = ...    # 新しい paper 属性を設定
del data['field_of_study']  # 'field_of_study' ノード型を削除
del data['has_topic']       # 'has_topic' エッジ型を削除
```

`metadata()` メソッドを呼び出すと，現在保持している全てのノード型・エッジ型の情報を取得できる．

```python
node_types, edge_types = data.metadata()
print(node_types)
['paper', 'author', 'institution']
print(edge_types)
[('paper', 'cites', 'paper'),
('author', 'writes', 'paper'),
('author', 'affiliated_with', 'institution')]
```

デバイス間の転送も，通常の PyTorch モジュールと同様の書き方で行える．

```python
data = data.to('cuda:0')
data = data.cpu()
```

孤立ノードの有無・自己ループの有無・無向グラフかどうかを判定するヘルパー関数も用意されている．

```python
data.has_isolated_nodes()
data.has_self_loops()
data.is_undirected()
```

`to_homogeneous()` を呼び出すことで，ヘテロジニアスなグラフ構造を単一の型からなるホモジニアスなグラフへ変換できる．このとき，型間で次元数が一致する特徴量は保持される．

```python
homogeneous_data = data.to_homogeneous()
print(homogeneous_data)
Data(x=[1879778, 128], edge_index=[2, 13605929], edge_type=[13605929])
```

変換後の `homogeneous_data.edge_type` は，各エッジが元々どの型に属していたかを整数値で表現したベクトルとなる．

## ヘテロジニアスグラフの変換

`ToUndirected()`，`AddSelfLoops()`，`NormalizeFeatures()` のような標準的な前処理変換（transform）は，ヘテロジニアスなデータオブジェクトに対してもそのまま適用可能である．

```python
import torch_geometric.transforms as T

data = T.ToUndirected()(data)
data = T.AddSelfLoops()(data)
data = T.NormalizeFeatures()(data)
```

- `ToUndirected()` は，逆方向のエッジを追加することで有向グラフを無向グラフへ変換し，双方向のメッセージパッシングを可能にする．この際，必要に応じて逆方向のエッジ型が新たに追加される．
- `AddSelfLoops()` は，各ノード型に対して自己ループのエッジを追加する．この自己ループには `(node_type, edge_type, node_type)` という適切なエッジ型が付与され，各ノードが自分自身からのメッセージを受け取れるようになる．
- `NormalizeFeatures()` はホモジニアスな場合と全く同様に機能し，指定した特徴量を型を問わず合計が1になるように正規化する．

## ヘテロジニアスGNNの作成

標準的なメッセージパッシング型のGNNは，そのままではヘテロジニアスグラフを処理できない．
なぜなら，異なる型のノード・エッジ特徴には，それぞれ異なる処理関数が必要となるためである．

一つの解決策は，エッジ型ごとに個別のメッセージ関数・更新関数を実装し，型ごとの辞書に対してループ処理を行うことである．
PyG は，このようなヘテロジニアスなメッセージパッシングGNN（MP-GNN）を作成するために，次の3つのアプローチを提供している．

1. `to_hetero()` または `to_hetero_with_bases()` を用いた，ホモジニアスモデルの自動変換
2. `HeteroConv` ラッパーを用いた，カスタム関数の定義
3. 既存のヘテロジニアス専用演算子の利用

### GNNモデルの自動変換

`to_hetero()` を用いると，メッセージ関数をエッジ型ごとに自動的に複製することで，ホモジニアスなアーキテクチャをヘテロジニアスなモデルへ変換できる．

```python
import torch_geometric.transforms as T
from torch_geometric.datasets import OGB_MAG
from torch_geometric.nn import SAGEConv, to_hetero


dataset = OGB_MAG(root='./data', preprocess='metapath2vec', transform=T.ToUndirected())
data = dataset[0]

class GNN(torch.nn.Module):
    def __init__(self, hidden_channels, out_channels):
        super().__init__()
        self.conv1 = SAGEConv((-1, -1), hidden_channels)
        self.conv2 = SAGEConv((-1, -1), out_channels)

    def forward(self, x, edge_index):
        x = self.conv1(x, edge_index).relu()
        x = self.conv2(x, edge_index)
        return x


model = GNN(hidden_channels=64, out_channels=dataset.num_classes)
model = to_hetero(model, data.metadata(), aggr='sum')
```

```python
with torch.no_grad():  # 遅延初期化されたモジュールを初期化する．
    out = model(data.x_dict, data.edge_index_dict)
```

変換後のモデルは，単一のテンソルではなく，ノード型・エッジ型をキーとした辞書を入力として受け取る．
`SAGEConv` に `(-1, -1)` のようなタプルを渡すことで，二部グラフ（bipartite graph）に対応したメッセージパッシングが可能になる．
チャンネル数に `-1` を指定する遅延初期化（lazy initialization）を利用すると，モデルへの最初の入力時にパラメータサイズが自動的に決定されるため，テンソルサイズを手動で追跡する必要がなくなる．
このアプローチは，スキップコネクションや jumping knowledge のような高度な技術もそのままサポートしている．

```python
from torch_geometric.nn import GATConv, Linear, to_hetero

class GAT(torch.nn.Module):
    def __init__(self, hidden_channels, out_channels):
        super().__init__()
        self.conv1 = GATConv((-1, -1), hidden_channels, add_self_loops=False)
        self.lin1 = Linear(-1, hidden_channels)
        self.conv2 = GATConv((-1, -1), out_channels, add_self_loops=False)
        self.lin2 = Linear(-1, out_channels)

    def forward(self, x, edge_index):
        x = self.conv1(x, edge_index) + self.lin1(x)
        x = x.relu()
        x = self.conv2(x, edge_index) + self.lin2(x)
        return x


model = GAT(hidden_channels=64, out_channels=dataset.num_classes)
model = to_hetero(model, data.metadata(), aggr='sum')
```

GAT の実装では，二部グラフにおいて自己ループの意味付けが曖昧になるため `add_self_loops=False` を指定して無効化しており，代わりに畳み込みと線形変換を組み合わせた学習可能なスキップコネクションを利用している．

```python
def train():
    model.train()
    optimizer.zero_grad()
    out = model(data.x_dict, data.edge_index_dict)
    mask = data['paper'].train_mask
    loss = F.cross_entropy(out['paper'][mask], data['paper'].y[mask])
    loss.backward()
    optimizer.step()
    return float(loss)
```

学習処理では，出力の辞書からノード型ごとにアクセスし，指定したマスクに対応する部分のみを用いて損失を計算する．

### Heterogeneous Convolution Wrapper の利用

`HeteroConv` ラッパーは，エッジ型をキーとしたサブモジュールの辞書を受け取ることができ，`to_hetero()` が全てのエッジ型に対して同一の演算子を複製するのに対して，エッジ型ごとに異なる演算子を個別に指定できる．
これにより，カスタムなヘテロジニアスアーキテクチャを柔軟に構築できる．

```python
import torch_geometric.transforms as T
from torch_geometric.datasets import OGB_MAG
from torch_geometric.nn import HeteroConv, GCNConv, SAGEConv, GATConv, Linear


dataset = OGB_MAG(root='./data', preprocess='metapath2vec', transform=T.ToUndirected())
data = dataset[0]

class HeteroGNN(torch.nn.Module):
    def __init__(self, hidden_channels, out_channels, num_layers):
        super().__init__()

        self.convs = torch.nn.ModuleList()
        for _ in range(num_layers):
            conv = HeteroConv({
                ('paper', 'cites', 'paper'): GCNConv(-1, hidden_channels),
                ('author', 'writes', 'paper'): SAGEConv((-1, -1), hidden_channels),
                ('paper', 'rev_writes', 'author'): GATConv((-1, -1), hidden_channels, add_self_loops=False),
            }, aggr='sum')
            self.convs.append(conv)

        self.lin = Linear(hidden_channels, out_channels)

    def forward(self, x_dict, edge_index_dict):
        for conv in self.convs:
            x_dict = conv(x_dict, edge_index_dict)
            x_dict = {key: x.relu() for key, x in x_dict.items()}
        return self.lin(x_dict['author'])

model = HeteroGNN(hidden_channels=64, out_channels=dataset.num_classes,
                  num_layers=2)
```

```python
with torch.no_grad():  # 遅延初期化されたモジュールを初期化する．
     out = model(data.x_dict, data.edge_index_dict)
```

上記の例では，論文同士の被引用関係（`cites`）には `GCNConv`，著者から論文への執筆関係（`writes`）には `SAGEConv`，逆方向の論文から著者への関係（`rev_writes`）には `GATConv` を利用している．
`aggr='sum'` は，複数のエッジ型から同一のターゲットノード型に集まったメッセージをどのように集約するかを指定するパラメータである．
このモデルも，学習ループに入る前に一度フォワードパスを実行することで，遅延初期化されたパラメータを確定させる必要がある．

### 既存のヘテロジニアス演算子を利用する

PyG は，`HGTConv`（Heterogeneous Graph Transformer）のような，ヘテロジニアスなグラフ専用に設計された演算子も提供している．
これらの演算子は，ラップすることなくカスタムモデルへ直接組み込むことができる．

```python
import torch_geometric.transforms as T
from torch_geometric.datasets import OGB_MAG
from torch_geometric.nn import HGTConv, Linear


dataset = OGB_MAG(root='./data', preprocess='metapath2vec', transform=T.ToUndirected())
data = dataset[0]

class HGT(torch.nn.Module):
    def __init__(self, hidden_channels, out_channels, num_heads, num_layers):
        super().__init__()

        self.lin_dict = torch.nn.ModuleDict()
        for node_type in data.node_types:
            self.lin_dict[node_type] = Linear(-1, hidden_channels)

        self.convs = torch.nn.ModuleList()
        for _ in range(num_layers):
            conv = HGTConv(hidden_channels, hidden_channels, data.metadata(),
                           num_heads, group='sum')
            self.convs.append(conv)

        self.lin = Linear(hidden_channels, out_channels)

    def forward(self, x_dict, edge_index_dict):
        for node_type, x in x_dict.items():
            x_dict[node_type] = self.lin_dict[node_type](x).relu_()

        for conv in self.convs:
            x_dict = conv(x_dict, edge_index_dict)

        return self.lin(x_dict['author'])

model = HGT(hidden_channels=64, out_channels=dataset.num_classes,
            num_heads=2, num_layers=2)
```

```python
with torch.no_grad():  # 遅延初期化されたモジュールを初期化する．
     out = model(data.x_dict, data.edge_index_dict)
```

この `HGT` の実装では，まずノード型ごとに個別の線形変換を適用し ReLU を通したうえで，`HGTConv` 層へ入力している．
`HGTConv` のコンストラクタは，隠れ層の次元数，（ノード型・エッジ型の情報を含む）メタデータ，アテンションヘッド数，集約方法（`group`）を受け取る．
このモデルについても，通常の遅延初期化と同様のパターンに従う．

## ヘテロジニアスグラフのサンプラー

PyG は，標準的な `NeighborLoader` や，専用の `HGTLoader` のような，ヘテロジニアスグラフに対するサンプリング機能を提供している．
サンプリングは，全ノードの近傍を処理することが計算量的に非現実的な大規模ヘテロジニアスグラフにおいて，効率的な表現学習を行うために不可欠である．
これらのサンプラーは，元のデータのサブセットを表す `HeteroData` を出力とし，主にサンプリング手法の点で異なる．
フルバッチ学習からミニバッチ学習への切り替えは，最小限のコード変更で行うことができる．
なお，`ClusterLoader` および `GraphSAINTLoader` のヘテロジニアス対応は，現在も開発中である．

```python
import torch_geometric.transforms as T
from torch_geometric.datasets import OGB_MAG
from torch_geometric.loader import NeighborLoader

transform = T.ToUndirected()  # 逆方向のエッジ型を追加する．
data = OGB_MAG(root='./data', preprocess='metapath2vec', transform=transform)[0]

train_loader = NeighborLoader(
    data,
    # 各ノード・各エッジ型について，2ホップ分，15個の近傍をサンプリングする．
    num_neighbors=[15] * 2,
    # "paper" 型の学習用ノードを，バッチサイズ128でサンプリングする．
    batch_size=128,
    input_nodes=('paper', data['paper'].train_mask),
)

batch = next(iter(train_loader))
```

`NeighborLoader` は，ホモジニアス・ヘテロジニアスいずれのグラフに対しても利用できる．
ヘテロジニアスなデータに対しては，エッジ型ごとに近傍サンプリング数を細かく指定することも可能である．

```python
num_neighbors = {key: [15] * 2 for key in data.edge_types}
```

`input_nodes` パラメータには，（ノード型，ブールマスク）のタプルを指定することで，サンプリングの起点となるノードを指定する．
これにより，例えば `data['paper'].train_mask` によって識別される学習用の論文ノードのように，特定のノード部分集合のみを起点として選択的にサンプリングできる．

```python
HeteroData(
  paper={
    x=[20799, 256],
    y=[20799],
    train_mask=[20799],
    val_mask=[20799],
    test_mask=[20799],
    batch_size=128
  },
  author={ x=[4419, 128] },
  institution={ x=[302, 128] },
  field_of_study={ x=[2605, 128] },
  (author, affiliated_with, institution)={ edge_index=[2, 0] },
  (author, writes, paper)={ edge_index=[2, 5927] },
  (paper, cites, paper)={ edge_index=[2, 11829] },
  (paper, has_topic, field_of_study)={ edge_index=[2, 10573] },
  (institution, rev_affiliated_with, author)={ edge_index=[2, 829] },
  (paper, rev_writes, author)={ edge_index=[2, 5512] },
  (field_of_study, rev_has_topic, paper)={ edge_index=[2, 10499] }
)
```

サンプリングされたバッチは，128個の論文ノードの埋め込みを計算するために，合計 28,187 個のノードを含んでいる．
ノードはサンプリングされた順序で並んでおり，先頭の `batch['paper'].batch_size` 個のノードが，元のミニバッチに含まれるノードそのものに対応する．そのため，出力からのスライスによって簡単に対象ノードのみを取り出すことができる．

```python
def train():
    model.train()

    total_examples = total_loss = 0
    for batch in train_loader:
        optimizer.zero_grad()
        batch = batch.to('cuda:0')
        batch_size = batch['paper'].batch_size
        out = model(batch.x_dict, batch.edge_index_dict)
        loss = F.cross_entropy(out['paper'][:batch_size],
                               batch['paper'].y[:batch_size])
        loss.backward()
        optimizer.step()

        total_examples += batch_size
        total_loss += float(loss) * batch_size

    return total_loss / total_examples
```

ミニバッチ学習は，ローダーが生成するバッチに対してループするという点を除けば，フルバッチ学習とほぼ同じである．
重要な点として，損失計算は先頭の `batch['paper'].batch_size` 個のノード（＝実際のミニバッチに含まれるノード）のみに限定する必要があり，近傍として取り込まれただけのノードは除外しなければならない．
そのため，予測結果である `out['paper']` とラベルである `batch['paper'].y` の両方を，バッチサイズでスライスする必要がある．
