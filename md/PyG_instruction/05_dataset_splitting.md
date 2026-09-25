# Dataset Splitting

- [Dataset Splitting](#dataset-splitting)
  - [Node Prediction](#node-prediction)
  - [Link Prediction](#link-prediction)
  - [Graph Prediction](#graph-prediction)
  - [Creating Custom Splits](#creating-custom-splits)

---

データセットの分割は，グラフ機械学習における重要なステップであり，データセットを学習・検証・テストの各サブセットに分割する作業のことである．これにより，モデルが適切に評価され，過学習が防止され，汎化性能が担保されることが保証される．このチュートリアルでは，データセット分割の基本を，ノード予測・リンク予測・グラフ予測という3つの基本タスクに焦点を当てて解説する．よく使われる手法である `RandomNodeSplit` と `RandomLinkSplit` の変換を紹介し，さらにランダムな分割以外のカスタムなデータセット分割の作成方法についても扱う．

## Node Prediction

> **Note**
>
> このセクションでは，PyG の `RandomNodeSplit` を使ってノードを学習・検証・テストセットへランダムに分割する方法を学ぶ．データセット `Planetoid` を用いた完全に動作するサンプルは [examples/cora.py](https://github.com/pyg-team/pytorch_geometric/blob/master/examples/cora.py) にある．

`RandomNodeSplit` は，PyG の `Data` オブジェクトと `HeteroData` オブジェクトの両方についてノードを分割するために初期化される．

- `split`：データセットの分割タイプを定義する．
- `num_splits`：追加する分割の数を定義する．
- `num_train_per_class`：クラスごとの学習ノード数を定義する．
- `num_val`：データ分割後の検証ノード数を定義する．
- `num_test`：データ分割後のテストノード数を定義する．
- `key`：正解ラベルの名前を定義する．

```python
import torch
from torch_geometric.data import Data
from torch_geometric.transforms import RandomNodeSplit

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
node_transform = RandomNodeSplit(num_val=2, num_test=3)
node_splits = node_transform(data)
```

ここでは，グラフデータをノードによって分割するために `RandomNodeSplit` 変換を初期化している．変換後，グラフデータには `train_mask`，`valid_mask`，`test_mask` が付与される．

```python
node_splits.train_mask
>>> tensor([ True, False, False, False, True, True, False, False])
node_splits.val_mask
>>> tensor([False, False, False, False, False, False, True, True])
node_splits.test_mask
>>> tensor([False, True, True, True, False, False, False, False])
```

この例では，8個のノードがあり，検証用に2ノード，テスト用に3ノードをサンプリングし，残りを学習用とする．最終的に，ノード `0, 4, 5` が学習セット，ノード `6, 7` が検証セット，ノード `1, 2, 3` がテストセットとなる．

## Link Prediction

> **Note**
>
> このセクションでは，PyG の `RandomLinkSplit` を使ってエッジを学習・検証・テストセットへランダムに分割する方法を学ぶ．データセット `Planetoid` を用いた完全に動作するサンプルは [examples/link_pred.py](https://github.com/pyg-team/pytorch_geometric/blob/master/examples/link_pred.py) にある．

`RandomLinkSplit` は，PyG の `Data` オブジェクトと `HeteroData` オブジェクトの両方についてエッジを分割するために初期化される．

- `num_val`：データ分割後の検証エッジ数を定義する．
- `num_test`：データ分割後のテストエッジ数を定義する．
- `is_undirected`：グラフを無向グラフとみなすかどうかを定義する．

```python
import torch
from torch_geometric.data import Data
from torch_geometric.transforms import RandomLinkSplit

x = torch.randn(8, 32)  # Node features of shape [num_nodes, num_features]
y = torch.randint(0, 4, (8, ))  # Node labels of shape [num_nodes]
edge_index = torch.tensor([
    [2, 3, 3, 4, 5, 6, 7],
    [0, 0, 1, 1, 2, 3, 4]],
)

edge_y = torch.tensor([0, 0, 0, 0, 1, 1, 1])
#   0  1
#  / \/ \
# 2  3  4
# |  |  |
# 5  6  7

data = Data(x=x, y=y, edge_index=edge_index, edge_y=edge_y)
edge_transform = RandomLinkSplit(num_val=0.2, num_test=0.2, key='edge_y',
                                is_undirected=False, add_negative_train_samples=False)
train_data, val_data, test_data = edge_transform(data)
```

ノード分割と同様に，グラフデータをエッジによって分割するために `RandomLinkSplit` 変換を初期化する．以下に分割結果を示す．

```python
train_data
>>> Data(x=[8, 32], edge_index=[2, 5], y=[8], edge_y=[5], edge_y_index=[2, 5])
val_data
>>> Data(x=[8, 32], edge_index=[2, 5], y=[8], edge_y=[2], edge_y_index=[2, 2])
test_data
>>> Data(x=[8, 32], edge_index=[2, 6], y=[8], edge_y=[2], edge_y_index=[2, 2])
```

`train_data.edge_index` と `val_data.edge_index` は，メッセージパッシングに使用されるエッジを指す．そのため，学習時および検証時には，学習用エッジに基づいて情報を伝播させることが許される．一方，テスト時には，学習用エッジと検証用エッジの和集合に基づいて情報を伝播させることができる．評価およびテストのためには，`val_data.edge_label_index` と `test_data.edge_label_index` が，モデルの評価・テストに使用すべき正例・負例サンプルのバッチを保持している．

## Graph Prediction

> **Note**
>
> このセクションでは，グラフを学習・検証・テストセットへランダムに分割する方法を学ぶ．データセット `PPI` を用いた完全に動作するサンプルは [examples/ppi.py](https://github.com/pyg-team/pytorch_geometric/blob/master/examples/ppi.py) にある．

グラフ予測タスクでは，各グラフが独立したサンプルとなる．通常，グラフデータセットを一定の比率に従って分割する必要がある．PyG は，`PPI` のように学習・検証・テスト用のインデックスをあらかじめ保持しているデータセットをいくつか提供している．

```python
from torch_geometric.datasets import PPI

path = './data/PPI'
train_dataset = PPI(path, split='train')
val_dataset = PPI(path, split='val')
test_dataset = PPI(path, split='test')
```

さらに，`scikit-learn` や `numpy` を使って PyG のデータセットをランダムに分割することもできる．

## Creating Custom Splits

ランダムな分割が特定のユースケースに適さない場合，カスタムなノード分割を作成することができる．この必要性は，実際のビジネスシナリオでよく発生する．例えば，EC（電子商取引）のシナリオには大規模なヘテロジニアスグラフが存在し，ノードはユーザー・商品・加盟店などを表現しうる．新規ユーザーに対するモデルの性能を評価するために，新規ユーザーと既存ユーザーを分けたいこともあるだろう．そのため，ここでは具体的な例は掲載しない．
