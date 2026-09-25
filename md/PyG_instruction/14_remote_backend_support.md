# Scaling Up GNNs via Remote Backends

- [Scaling Up GNNs via Remote Backends](#scaling-up-gnns-via-remote-backends)
  - [Background](#background)
  - [Feature Store](#feature-store)
  - [Graph Store and Sampler](#graph-store-and-sampler)
  - [Data Loader](#data-loader)
  - [Putting it All Together](#putting-it-all-together)

---

PyG（バージョン2.2以降）は，スケーラブルなグラフ機械学習のためのシンプルなパラダイムと容易に統合できる，数多くのプリミティブを備えている．
これにより，ユーザーは自身のマシンが利用可能なメモリサイズをはるかに超える大きさのグラフ上で GNN を学習できるようになる．
これを実現するために，既存の使い慣れた PyG インターフェースへ直接組み込める，シンプルで使いやすく拡張性の高い [`torch_geometric.data.FeatureStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.FeatureStore.html#torch_geometric.data.FeatureStore) と [`torch_geometric.data.GraphStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.GraphStore.html#torch_geometric.data.GraphStore) の抽象化を導入している．
[`FeatureStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.FeatureStore.html#torch_geometric.data.FeatureStore) を定義することで，ユーザーはリモートに保存されたノード（そして近い将来にはエッジも）の特徴量を活用できるようになり，[`GraphStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.GraphStore.html#torch_geometric.data.GraphStore) を定義することで，リモートに保存されたグラフ構造情報を活用できるようになる．
この2つを組み合わせることで，開発者の負担を抑えつつ，強力な GNN のスケーラビリティを実現できる．

> **Warning**
> ここで説明するリモートバックエンドの API は，使いやすさと汎用性を継続的に改善していく過程で，将来的に変更される可能性がある．

> **Note**
> 現時点では，[`FeatureStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.FeatureStore.html#torch_geometric.data.FeatureStore) と [`GraphStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.GraphStore.html#torch_geometric.data.GraphStore) は *heterogeneous graphs*（ヘテロジニアスグラフ）のみをサポートしており，エッジ特徴量には対応していない．ホモジニアスグラフおよびエッジ特徴量のサポートは近日中に追加される予定である．

## Background

実際にインスタンス化された Graph Neural Network は，次の2種類のデータから構成される．

- **ノードおよび／またはエッジの特徴量情報：** グラフ中のノードやエッジの属性に対応する密なベクトル
- **グラフ構造情報：** グラフ中のノードと，それらを結ぶエッジ

GNN についてまず言えるのは，選択したアクセラレータの利用可能なメモリを超える規模のデータへスケールするには，グラフ全体を一度に扱う（フルバッチ学習）のではなく，サンプリングされたサブグラフ（これがミニバッチを構成する）上で学習する必要があるということである．この手法は学習プロセスに確率性を加える一方で，アクセラレータに要求されるメモリ量をサンプリングされたサブグラフのそれにまで削減できる．

[![../_images/remote_1.png](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/_images/remote_1.png)](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/_images/remote_1.png)

*図1：古典的なミニバッチ GNN 学習のパラダイム．*

しかし，ミニバッチ学習は選択したアクセラレータに要求されるメモリ量を削減する一方で，グラフ学習のスケーラビリティに関するあらゆる問題を解決する万能薬ではない．特に，学習プロセスの各イテレーションでアクセラレータへ渡すサブグラフをサンプリングする必要があるため，従来はグラフと特徴量をユーザーのマシンの CPU DRAM に保存しておく必要があった．大規模な場合，この要件はかなりの負担となりうる．

- グラフと特徴量を保存するのに十分な CPU DRAM を備えたインスタンスを確保するのは難しい
- データ並列で学習を行うには，各計算ノードにグラフと特徴量を複製する必要がある
- グラフと特徴量は，単一マシンのメモリよりもはるかに大きくなりうる

したがって，単一マシンのメモリ要件を超える非常に大きなグラフや特徴量へスケールするには，これらのデータ構造をアウトオブコア化し，計算を行うノード上ではサンプリングされたサブグラフのみを処理するようにする必要がある．この目標を達成するために，PyG は特徴量情報とグラフ構造を保存するための2つの主要な抽象化に依拠している．特徴量は，効率的なランダムアクセスをサポートする必要があるキーバリュー形式の [`FeatureStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.FeatureStore.html#torch_geometric.data.FeatureStore) に保存される．グラフ情報は，[`GraphStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.GraphStore.html#torch_geometric.data.GraphStore) インスタンス上で動作するように定義されたサンプラーのために効率的なサンプリングをサポートする必要がある [`GraphStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.GraphStore.html#torch_geometric.data.GraphStore) に保存される．

[![../_images/remote_2.png](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/_images/remote_2.png)](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/_images/remote_2.png)

*図2：リモートストレージと学習インスタンスの間のグラフデータ保存レイアウト．*

PyG（バージョン2.2以降）では，グラフデータを特徴量と構造情報に分離すること，これらの情報を実際の学習ノードから見て（場合によっては）リモートな場所に保存すること，そしてこれらのコンポーネント間のやり取りは，すべてエンドユーザーから完全に抽象化されている．[`FeatureStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.FeatureStore.html#torch_geometric.data.FeatureStore) と [`GraphStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.GraphStore.html#torch_geometric.data.GraphStore) が（前述のパフォーマンス要件を踏まえて）適切に定義されている限り，残りの処理はすべて PyG が引き受ける！

## Feature Store

[`torch_geometric.data.FeatureStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.FeatureStore.html#torch_geometric.data.FeatureStore) は，グラフのノードとエッジの特徴量を保持する．グラフのレイアウト情報（すなわち `edge_index`）を保存するのは比較的安価（1エッジあたり約32バイト）であるため，グラフ学習アプリケーションにおいては特徴量の保存がストレージのボトルネックとなることが多い．PyG は，さまざまな [`FeatureStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.FeatureStore.html#torch_geometric.data.FeatureStore) 実装がそのコアとなる学習 API とやり取りするための共通インターフェースを提供している．

[`FeatureStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.FeatureStore.html#torch_geometric.data.FeatureStore) の実装の詳細は，CRUD ライクなインターフェースを通じて PyG から抽象化されている．具体的には，[`FeatureStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.FeatureStore.html#torch_geometric.data.FeatureStore) 抽象クラスの実装者は，主に [`put_tensor()`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.FeatureStore.html#torch_geometric.data.FeatureStore.put_tensor)，[`get_tensor()`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.FeatureStore.html#torch_geometric.data.FeatureStore.get_tensor)，[`remove_tensor()`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.FeatureStore.html#torch_geometric.data.FeatureStore.remove_tensor) の各機能をオーバーライドすることが想定されている．これにより，PyG は実装側に保存された特徴量を活用できるようになると同時に，ユーザーは Python らしいインターフェースを用いて [`FeatureStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.FeatureStore.html#torch_geometric.data.FeatureStore) の要素を検査・変更できるようになる．

```python
feature_store = CustomFeatureStore()

paper_features = ...  # [num_papers, num_paper_features]
author_features = ...  # [num_authors, num_author_features]

# Add features:
feature_store['paper', 'x', None] = paper_features
feature_store['author', 'x', None] = author_features

# Access features:
assert torch.equal(feature_store['paper', 'x'], paper_features)
assert torch.equal(feature_store['paper'].x, paper_features)
assert torch.equal(feature_store['author', 'x', 0:20], author_features[0:20])
```

[`FeatureStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.FeatureStore.html#torch_geometric.data.FeatureStore) 抽象化の一般的な実装はキーバリューストアであり，例えば `memcached`，`LevelDB`，`RocksDB` といったバックエンドはいずれも高性能な選択肢として利用可能である．

## Graph Store and Sampler

[`torch_geometric.data.GraphStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.GraphStore.html#torch_geometric.data.GraphStore) は，グラフ中のノード間の関係を定義するエッジインデックスを保持する．[`GraphStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.GraphStore.html#torch_geometric.data.GraphStore) の目的は，開発者が選択したサンプリングアルゴリズムに従って，起点となるノードから効率的にサンプリングできるような形でグラフ情報を保存することである．

[`FeatureStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.FeatureStore.html#torch_geometric.data.FeatureStore) と同様に，PyG はさまざまな [`GraphStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.GraphStore.html#torch_geometric.data.GraphStore) 実装がそのコアとなる学習 API とやり取りするための共通インターフェースを提供している．しかし [`FeatureStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.FeatureStore.html#torch_geometric.data.FeatureStore) とは異なり，[`GraphStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.GraphStore.html#torch_geometric.data.GraphStore) はすべての要素に対して効率的なランダムアクセスを提供する必要はなく，むしろ効率的なサブグラフサンプリングを可能にする表現を定義する必要がある．このインターフェースの使用例を以下に示す．

```python
graph_store = CustomGraphStore()

edge_index = torch.tensor([[0, 1, 1, 2], [1, 0, 2, 1]])

# Put edges:
graph_store['edge', 'coo'] = coo

# Access edges:
row, col = graph_store['edge', 'coo']
assert torch.equal(row, edge_index[0])
assert torch.equal(col, edge_index[1])
```

[`GraphStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.GraphStore.html#torch_geometric.data.GraphStore) の一般的な実装はグラフデータベースであり，例えば `Neo4j`，`TigerGraph`，`ArangoDB`，`Kùzu` といったものはいずれも高性能な選択肢として利用可能である．PyG を `Kùzu` データベースと組み合わせて利用する例を[こちら](https://github.com/pyg-team/pytorch_geometric/tree/master/examples/distributed/kuzu)で提供している．

グラフサンプラーは，与えられた [`GraphStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.GraphStore.html#torch_geometric.data.GraphStore) と密接に結びついており，その [`GraphStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.GraphStore.html#torch_geometric.data.GraphStore) 上で動作して，入力ノードからサンプリングされたサブグラフを生成する．異なるサンプリングアルゴリズムは，[`torch_geometric.sampler.BaseSampler`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/modules/sampler.html#torch_geometric.sampler.BaseSampler) インターフェースの背後にそれぞれ実装されている．デフォルトでは，PyG のデフォルトのインメモリサンプラーは，[`GraphStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.GraphStore.html#torch_geometric.data.GraphStore) からすべてのエッジインデックスを学習ノードのメモリへ取り込み，それらを圧縮スパース列（CSC）形式に変換したうえで，あらかじめ組み込まれたインメモリのサンプリングルーチンを活用する．しかし，カスタムのサンプラー実装では，効率上の理由（例えば，リモートの [`GraphStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.GraphStore.html#torch_geometric.data.GraphStore) に対して直接サンプリングを行う場合など）から，[`BaseSampler`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/modules/sampler.html#torch_geometric.sampler.BaseSampler) クラスの [`sample_from_nodes()`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/modules/sampler.html#torch_geometric.sampler.BaseSampler.sample_from_nodes) および／または [`sample_from_edges()`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/modules/sampler.html#torch_geometric.sampler.BaseSampler.sample_from_edges) を実装することで，[`GraphStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.GraphStore.html#torch_geometric.data.GraphStore) の専用メソッドを呼び出すという選択も可能である．

```python
# `CustomGraphSampler` knows how to sample on `CustomGraphStore`:
node_sampler = CustomGraphSampler(
    graph_store=graph_store,
    num_neighbors=[10, 20],
    ...
)
```

## Data Loader

PyG は，[`GraphStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.GraphStore.html#torch_geometric.data.GraphStore) が実装しなければならないサンプリング用のドメイン固有言語を定義しているわけではない．むしろ，サンプラーと [`GraphStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.GraphStore.html#torch_geometric.data.GraphStore) はデータローダーを介して密接に結び付けられている．

PyG は，標準で2種類のデータローダーを提供している．1つはノード分類タスクで使用するために入力ノードからサブグラフをサンプリングする [`torch_geometric.loader.NodeLoader`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/modules/loader.html#torch_geometric.loader.NodeLoader)，もう1つはリンク予測タスクで使用するためにエッジの両端からサブグラフをサンプリングする [`torch_geometric.loader.LinkLoader`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/modules/loader.html#torch_geometric.loader.LinkLoader) である．これらのデータローダーは，入力として [`FeatureStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.FeatureStore.html#torch_geometric.data.FeatureStore)，[`GraphStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.GraphStore.html#torch_geometric.data.GraphStore)，およびグラフサンプラーを必要とし，内部でサンプラーの [`sample_from_nodes()`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/modules/sampler.html#torch_geometric.sampler.BaseSampler.sample_from_nodes) または [`sample_from_edges()`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/modules/sampler.html#torch_geometric.sampler.BaseSampler.sample_from_edges) メソッドを呼び出してサブグラフサンプリングを行う．

```python
# Instead of passing PyG data objects, we now pass a tuple
# of the `FeatureStore` and `GraphStore as input data:
loader = NodeLoader(
    data=(feature_store, graph_store),
    node_sampler=node_sampler,
    batch_size=20,
    input_nodes='paper',
)

for batch in loader:
    pass
```

## Putting it All Together

大まかに言えば，上記で挙げたコンポーネントはすべて協調して動作することで，PyG 内で GNN をスケールアップするためのサポートを提供している．

- **データローダー**（正確にはワーカーごと）が [`BaseSampler`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/modules/sampler.html#torch_geometric.sampler.BaseSampler) を利用して [`GraphStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.GraphStore.html#torch_geometric.data.GraphStore) へサンプリングリクエストを送る．
- 応答を受け取ると，データローダーは続けて，サンプリングされたサブグラフのノードとエッジに関連する特徴量を [`FeatureStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.FeatureStore.html#torch_geometric.data.FeatureStore) へ問い合わせる．
- データローダーは，グラフ構造情報と特徴量情報から最終的なミニバッチを構築し，フォワード／バックワードパスのためにアクセラレータへ送る．
- 収束するまでこれを繰り返す．

ここで概説したクラスはいずれも共通のインターフェースを通じてやり取りするため，拡張性・汎用性が高く，普段利用している PyG へも容易に統合できる．

[![../_images/remote_3.png](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/_images/remote_3.png)](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/_images/remote_3.png)

*図3：[`FeatureStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.FeatureStore.html#torch_geometric.data.FeatureStore)，[`GraphStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.GraphStore.html#torch_geometric.data.GraphStore)，グラフサンプラー，データローダーを結び付ける共通インターフェース（およびデータフロー）．*

スケーラビリティに取り組み始めるには，上記で挙げたインターフェースを確認し，それらの背後で独自の [`FeatureStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.FeatureStore.html#torch_geometric.data.FeatureStore)，[`GraphStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.GraphStore.html#torch_geometric.data.GraphStore)，[`BaseSampler`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/modules/sampler.html#torch_geometric.sampler.BaseSampler) の実装を定義することを推奨する．[`FeatureStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.FeatureStore.html#torch_geometric.data.FeatureStore)，[`GraphStore`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.data.GraphStore.html#torch_geometric.data.GraphStore)，[`BaseSampler`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/modules/sampler.html#torch_geometric.sampler.BaseSampler) が正しく実装されていれば，あとはそれらを [`NodeLoader`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/modules/loader.html#torch_geometric.loader.NodeLoader) または [`LinkLoader`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/modules/loader.html#torch_geometric.loader.LinkLoader) のパラメータとして渡すだけでよく，それ以外の PyG の処理はすべて，純粋なインメモリのアプリケーションと同様にシームレスに動作する．

この機能は現在も活発に開発が進められている段階であるため，質問・コメント・懸念点などがあれば，[GitHub](https://github.com/pyg-team/pytorch_geometric/discussions) または [Slack](https://data.pyg.org/slack.html) で気軽に PyG のコアチームへ連絡してほしい．
