# Explaining Graph Neural Networks

- [Explaining Graph Neural Networks](#explaining-graph-neural-networks)
  - [Explainer Interface](#explainer-interface)
  - [Examples](#examples)
    - [Explaining node classification on a homogeneous graph](#explaining-node-classification-on-a-homogeneous-graph)
    - [Explaining node classification on a heterogeneous graph](#explaining-node-classification-on-a-heterogeneous-graph)
    - [Explaining graph regression on a homogeneous graph](#explaining-graph-regression-on-a-homogeneous-graph)

---

GNN モデルを解釈することは，多くのユースケースにおいて重要である．
PyG（2.3 以降）は，第一級（first-class）の GNN 解釈可能性サポートのために `torch_geometric.explain` パッケージを提供しており，現時点で次を含む．

- [`Explainer`](../modules/explain.html#torch_geometric.explain.Explainer) クラスを通じて，さまざまな説明（explanation）を生成するための柔軟なインターフェース，
- [`GNNExplainer`](../generated/torch_geometric.explain.algorithm.GNNExplainer.html#torch_geometric.explain.algorithm.GNNExplainer)，[`PGExplainer`](../generated/torch_geometric.explain.algorithm.PGExplainer.html#torch_geometric.explain.algorithm.PGExplainer)，[`CaptumExplainer`](../generated/torch_geometric.explain.algorithm.CaptumExplainer.html#torch_geometric.explain.algorithm.CaptumExplainer) など，複数の基盤となる説明アルゴリズム，
- [`Explanation`](../modules/explain.html#torch_geometric.explain.Explanation) クラスまたは [`HeteroExplanation`](../modules/explain.html#torch_geometric.explain.HeteroExplanation) クラスを通じた説明の可視化サポート，
- そして，`metric` パッケージを通じて説明を評価するための指標．

> **Warning**
>
> ここで説明する説明用 API は，使いやすさと汎用性を改善し続ける取り組みの中で，今後変更される可能性がある．

## Explainer Interface

[`torch_geometric.explain.Explainer`](../modules/explain.html#torch_geometric.explain.Explainer) クラスは，解釈可能性に関するすべてのパラメータを扱うよう設計されている（詳細は [`ExplainerConfig`](../modules/explain.html#torch_geometric.explain.config.ExplainerConfig) クラスを参照）．

- `torch_geometric.explain.algorithm` モジュールのどのアルゴリズムを使用するか（例：[`GNNExplainer`](../generated/torch_geometric.explain.algorithm.GNNExplainer.html#torch_geometric.explain.algorithm.GNNExplainer)）
- 計算する説明のタイプ，すなわちデータセットの背後にある現象を説明するための `explanation_type="phenomenon"` と，GNN モデルの予測を説明するための `explanation_type="model"`（詳細は [“GraphFramEx: Towards Systematic Evaluation of Explainability Methods for Graph Neural Networks”](https://arxiv.org/abs/2206.09677) 論文を参照）．
- ノードおよびエッジに対するマスクの種類（例：`mask="object"` や `mask="attributes"`）
- マスクに対する任意の後処理（例：`threshold_type="topk"` や `threshold_type="hard"`）

このクラスにより，ユーザーは異なる解釈可能性手法を容易に比較したり，異なる種類のマスクを簡単に切り替えたりしながら，高水準のフレームワークを同じに保つことができる．
[`Explainer`](../modules/explain.html#torch_geometric.explain.Explainer) は，GNN モデルを説明する上でどのノード・エッジ・特徴が重要であるかについての最終的な情報を含む [`Explanation`](../modules/explain.html#torch_geometric.explain.Explanation) オブジェクトまたは [`HeteroExplanation`](../modules/explain.html#torch_geometric.explain.HeteroExplanation) オブジェクトを生成する．

> **Note**
>
> `torch_geometric.explain` パッケージについては，この[ブログ記事](https://medium.com/@pytorch_geometric/graph-machine-learning-explainability-with-pyg-ff13cffc23c2)で詳しく読むことができる．

## Examples

以下では，対応するコード例とともにいくつかのユースケースを説明する．

### Explaining node classification on a homogeneous graph

ホモジニアスグラフ上でノード分類を行う GNN の `model` があるとする．
[`torch_geometric.explain.algorithm.GNNExplainer`](../generated/torch_geometric.explain.algorithm.GNNExplainer.html#torch_geometric.explain.algorithm.GNNExplainer) アルゴリズムを使って，[`Explanation`](../modules/explain.html#torch_geometric.explain.Explanation) を生成できる．
[`Explainer`](../modules/explain.html#torch_geometric.explain.Explainer) を，`node_mask_type` と `edge_mask_type` の両方を使用するよう設定し，最終的な [`Explanation`](../modules/explain.html#torch_geometric.explain.Explanation) オブジェクトが (1) `node_mask`（予測にとってどのノードと特徴が重要かを示す）と (2) `edge_mask`（予測にとってどのエッジが重要かを示す）を含むようにする．

```python
from torch_geometric.data import Data
from torch_geometric.explain import Explainer, GNNExplainer

data = Data(...)  # A homogeneous graph data object.

explainer = Explainer(
    model=model,
    algorithm=GNNExplainer(epochs=200),
    explanation_type='model',
    node_mask_type='attributes',
    edge_mask_type='object',
    model_config=dict(
        mode='multiclass_classification',
        task_level='node',
        return_type='log_probs',  # Model returns log probabilities.
    ),
)

# Generate explanation for the node at index `10`:
explanation = explainer(data.x, data.edge_index, index=10)
print(explanation.edge_mask)
print(explanation.node_mask)
```

最後に，説明における特徴の重要度と，重要な部分グラフの両方を可視化できる．

```python
explanation.visualize_feature_importance(top_k=10)

explanation.visualize_graph()
```

[`GNNExplainer`](../generated/torch_geometric.explain.algorithm.GNNExplainer.html#torch_geometric.explain.algorithm.GNNExplainer) による説明を評価するために，`torch_geometric.explain.metric` モジュールを利用できる．
例えば，ある説明の [`unfaithfulness()`](../generated/torch_geometric.explain.metric.unfaithfulness.html#torch_geometric.explain.metric.unfaithfulness) を計算するには，次のように実行する．

```python
from torch_geometric.explain import unfaithfulness

metric = unfaithfulness(explainer, explanation)
print(metric)
```

### Explaining node classification on a heterogeneous graph

ヘテロジニアスグラフ上でノード分類を行うヘテロジニアス GNN の `model` があるとする．
[`torch_geometric.explain.algorithm.CaptumExplainer`](../generated/torch_geometric.explain.algorithm.CaptumExplainer.html#torch_geometric.explain.algorithm.CaptumExplainer) アルゴリズムを介して，[Captum](https://captum.ai/docs/extension/integrated_gradients) の `IntegratedGradient` 帰属（attribution）手法を使用し，[`HeteroExplanation`](../modules/explain.html#torch_geometric.explain.HeteroExplanation) を生成できる．

> **Note**
>
> [`CaptumExplainer`](../generated/torch_geometric.explain.algorithm.CaptumExplainer.html#torch_geometric.explain.algorithm.CaptumExplainer) は，[Captum](https://captum.ai) ライブラリのラッパーであり，任意のホモジニアスあるいはヘテロジニアスな PyG モデルを説明するために，ほとんどの帰属手法をサポートしている．

[`Explainer`](../modules/explain.html#torch_geometric.explain.Explainer) を，`node_mask_type` と `edge_mask_type` の両方を使用するよう設定し，最終的な [`HeteroExplanation`](../modules/explain.html#torch_geometric.explain.HeteroExplanation) オブジェクトが (1) *各* ノードタイプについての `node_mask`（各ノードタイプにおいてどのノードと特徴が予測にとって重要かを示す）と (2) *各* エッジタイプについての `edge_mask`（各エッジタイプにおいてどのエッジが予測にとって重要かを示す）を含むようにする．

```python
from torch_geometric.data import HeteroData
from torch_geometric.explain import Explainer, CaptumExplainer

hetero_data = HeteroData(...)  # A heterogeneous graph data object.

explainer = Explainer(
    model,  # It is assumed that model outputs a single tensor.
    algorithm=CaptumExplainer('IntegratedGradients'),
    explanation_type='model',
    node_mask_type='attributes',
    edge_mask_type='object',
    model_config = dict(
        mode='multiclass_classification',
        task_level=task_level,
        return_type='probs',  # Model returns probabilities.
    ),
)

# Generate batch-wise heterogeneous explanations for
# the nodes at index `1` and `3`:
hetero_explanation = explainer(
    hetero_data.x_dict,
    hetero_data.edge_index_dict,
    index=torch.tensor([1, 3]),
)
print(hetero_explanation.edge_mask_dict)
print(hetero_explanation.node_mask_dict)
```

### Explaining graph regression on a homogeneous graph

ホモジニアスグラフ上でグラフ回帰を行う GNN の `model` があるとする．
[`torch_geometric.explain.algorithm.PGExplainer`](../generated/torch_geometric.explain.algorithm.PGExplainer.html#torch_geometric.explain.algorithm.PGExplainer) アルゴリズムを使って，[`Explanation`](../modules/explain.html#torch_geometric.explain.Explanation) を生成できる．
[`Explainer`](../modules/explain.html#torch_geometric.explain.Explainer) を `edge_mask_type` を使用するよう設定し，最終的な [`Explanation`](../modules/explain.html#torch_geometric.explain.Explanation) オブジェクトが，予測にとってどのエッジが重要かを示す `edge_mask` を含むようにする．
重要な点として，[`Explainer`](../modules/explain.html#torch_geometric.explain.Explainer) に `node_mask_type` を渡すとエラーになる．なぜなら，[`PGExplainer`](../generated/torch_geometric.explain.algorithm.PGExplainer.html#torch_geometric.explain.algorithm.PGExplainer) はノードの重要度を説明できないためである．

```python
from torch_geometric.data import Data
from torch_geometric.explain import Explainer, PGExplainer

dataset = ...
loader = DataLoader(dataset, batch_size=1, shuffle=True)

explainer = Explainer(
    model=model,
    algorithm=PGExplainer(epochs=30, lr=0.003),
    explanation_type='phenomenon',
    edge_mask_type='object',
    model_config=dict(
        mode='regression',
        task_level='graph',
        return_type='raw',
    ),
    # Include only the top 10 most important edges:
    threshold_config=dict(threshold_type='topk', value=10),
)

# PGExplainer needs to be trained separately since it is a parametric
# explainer i.e it uses a neural network to generate explanations:
for epoch in range(30):
    for batch in loader:
        loss = explainer.algorithm.train(
            epoch, model, batch.x, batch.edge_index, target=batch.target)

# Generate the explanation for a particular graph:
explanation = explainer(dataset[0].x, dataset[0].edge_index)
print(explanation.edge_mask)
```

この機能はまだ活発に開発が続けられているため，質問・コメント・懸念点があれば，[GitHub](https://github.com/pyg-team/pytorch_geometric/discussions) や [Slack](https://data.pyg.org/slack.html) を通じて PyG のコアチームまでお気軽にご連絡いただきたい．
