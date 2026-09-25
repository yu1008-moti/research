# Compiled Graph Neural Networks

- [Compiled Graph Neural Networks](#compiled-graph-neural-networks)
  - [Basic Usage](#basic-usage)
  - [Maximizing Performance](#maximizing-performance)
  - [Example Scripts](#example-scripts)
  - [Benchmark](#benchmark)

---

`torch.compile()` は，`torch >= 2.0.0` において PyTorch コードを高速化するための最新の手法である．
`torch.compile()` は，最小限のコード変更のみで，最適化されたカーネルへ JIT コンパイルすることによって PyTorch コードの実行を高速化する．

内部的には，`torch.compile()` は `TorchDynamo` を介して PyTorch プログラムをキャプチャし，`PrimTorch` を介して2,000種類を超える PyTorch 演算子を正規化したうえで，最終的にディープラーニングコンパイラである `TorchInductor` を介して，複数のアクセラレータ・バックエンドにまたがる高速なコードを生成する．

> **Note**
> `torch.compile()` の活用方法についての一般的なチュートリアルは[こちら](https://pytorch.org/tutorials/intermediate/torch_compile_tutorial.html)，そのインターフェースの説明は[こちら](https://pytorch.org/docs/stable/generated/torch.compile.html)を参照．

このチュートリアルでは，`torch.compile()` を用いて，自作の PyG モデルを最適化する方法を示す．

> **Note**
> PyG 2.5 以降では，`torch.compile()` はすべての PyG GNN レイヤーと完全に互換性を持つようになった．
> それより前のバージョンの PyG を使用している場合は，代わりに `torch_geometric.compile()` の利用を検討すること．

## Basic Usage

PyG モデルを定義済みであれば，それを `torch.compile()` でラップするだけで，最適化されたバージョンを得ることができる．

```python
import torch
from torch_geometric.nn import GraphSAGE

model = GraphSAGE(in_channels, hidden_channels, num_layers, out_channels)
model = model.to(device)

model = torch.compile(model)
```

そして，通常通りに実行する．

```python
from torch_geometric.datasets import Planetoid

dataset = Planetoid(root, name="Cora")
data = dataset[0].to(device)

out = model(data.x, data.edge_index)
```

## Maximizing Performance

`torch.compile()` メソッドには，把握しておくべき2つの重要な引数がある．

- PyG で扱われるミニバッチの多くは，その性質上動的であり，ミニバッチごとに形状（shape）が変化する．このようなケースでは，`dynamic=True` 引数を用いることで，PyTorch における動的形状（dynamic shape）のトレースを強制できる．

  ```python
  torch.compile(model, dynamic=True)
  ```

  これにより，PyTorch はミニバッチ間でサイズが変化しても再コンパイルが発生しないよう，あらかじめ可能な限り動的なカーネルを生成しようと試みる．なお，`dynamic` を [`False`](https://docs.python.org/3/library/constants.html#False) に設定した場合，PyTorch は動的カーネルを*決して*生成しなくなるため，（例えば小規模グラフでのフルバッチ学習のように）グラフサイズが変化しないことが保証されている場合にのみ動作する．デフォルトでは，PyTorch `>= 2.1.0` において `dynamic` は [`None`](https://docs.python.org/3/library/constants.html#None) に設定されており，PyTorch は動的性（dynamism）が発生したかどうかを自動的に検出する．なお，動的形状トレースのサポートには PyTorch `>= 2.1.0` のインストールが必要である．

- 高速化を最大限に得るためには，コンパイル済みモデル中のグラフブレイク（graph break）を極力抑える必要がある．`fullgraph=True` 引数を用いることで，最初にグラフブレイクが発生した時点でエラーを発生させ，コンパイルを強制することができる．

  ```python
  torch.compile(model, fullgraph=True)
  ```

  作成したモデルにグラフブレイクが含まれていないことを確認するのは，一般的に良い習慣である．重要な点として，PyG には現時点でグラフブレイクを引き起こす演算がいくつか存在する（ただし回避策は存在する）．例えば，

  1. [`global_mean_pool()`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.nn.pool.global_mean_pool.html#torch_geometric.nn.pool.global_mean_pool)（および他のプーリング演算子）は，バッチサイズ `size` が渡されない場合にデバイス同期を行うため，グラフブレイクを引き起こす．
  2. [`remove_self_loops()`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/modules/utils.html#torch_geometric.utils.remove_self_loops) および [`add_remaining_self_loops()`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/modules/utils.html#torch_geometric.utils.add_remaining_self_loops) は，与えられた `edge_index` にマスクを適用するため，最終的な出力形状を計算する際にデバイス同期が発生する．そのため，GNN へ入力する*前*にグラフを加工しておくこと（例えば，[`AddSelfLoops`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.transforms.AddSelfLoops.html#torch_geometric.transforms.AddSelfLoops) や [`GCNNorm`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.transforms.GCNNorm.html#torch_geometric.transforms.GCNNorm) といった変換（transform）を用いる）や，[`GCNConv`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.nn.conv.GCNConv.html#torch_geometric.nn.conv.GCNConv) のようなレイヤーを初期化する際に `add_self_loops=False`／`normalize=False` を設定しておくことを推奨する．

## Example Scripts

`torch.compile()` の実践的な使用例をさらに示すため，`examples/compile` に複数のサンプルを収録している．

1. [`GCN`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.nn.models.GCN.html#torch_geometric.nn.models.GCN)（`dynamic=False`）による[ノード分類](https://github.com/pyg-team/pytorch_geometric/blob/master/examples/compile/gcn.py)
2. [`GIN`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.nn.models.GIN.html#torch_geometric.nn.models.GIN)（`dynamic=True`）による[グラフ分類](https://github.com/pyg-team/pytorch_geometric/blob/master/examples/compile/gin.py)

特定の PyG モデルにおいて `torch.compile()` が失敗することに気づいた場合は，遠慮なく [GitHub](https://github.com/pyg-team/pytorch_geometric/issues) または [Slack](https://data.pyg.org/slack.html) で連絡してほしい．PyG コードベース全体における `torch.compile()` のサポートを改善することに，我々は強い意欲を持っている．

## Benchmark

`torch.compile()` は，多くの PyG モデルにおいて**驚くほどうまく**機能する．**全体として，最大で300%の実行時間の改善が確認されている．**

具体的には，[`GCN`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.nn.models.GCN.html#torch_geometric.nn.models.GCN)，[`GraphSAGE`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.nn.models.GraphSAGE.html#torch_geometric.nn.models.GraphSAGE)，[`GIN`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.nn.models.GIN.html#torch_geometric.nn.models.GIN) をベンチマークし，従来の eager モードと `torch.compile()` から得られる実行時間を比較する．10,000個のノードと200,000本のエッジを持つ合成グラフを用い，隠れ層の特徴次元数は64とする．500回の最適化ステップにわたる実行時間を報告する．

| Model | Mode | Forward | Backward | Total | Speedup |
| --- | --- | --- | --- | --- | --- |
| [`GCN`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.nn.models.GCN.html#torch_geometric.nn.models.GCN) | Eager | 2.6396s | 2.1697s | 4.8093s | |
| [`GCN`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.nn.models.GCN.html#torch_geometric.nn.models.GCN) | **Compiled** | **1.1082s** | **0.5896s** | **1.6978s** | **2.83x** |
| [`GraphSAGE`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.nn.models.GraphSAGE.html#torch_geometric.nn.models.GraphSAGE) | Eager | 1.6023s | 1.6428s | 3.2451s | |
| [`GraphSAGE`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.nn.models.GraphSAGE.html#torch_geometric.nn.models.GraphSAGE) | **Compiled** | **0.7033s** | **0.7465s** | **1.4498s** | **2.24x** |
| [`GIN`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.nn.models.GIN.html#torch_geometric.nn.models.GIN) | Eager | 1.6701s | 1.6990s | 3.3690s | |
| [`GIN`](https://pytorch-geometric.readthedocs.io/en/2.8.0.post1/generated/torch_geometric.nn.models.GIN.html#torch_geometric.nn.models.GIN) | **Compiled** | **0.7320s** | **0.7407s** | **1.4727s** | **2.29x** |

これらの結果を再現するには，以下を実行する．

```python
python test/nn/models/test_basic_gnn.py
```

GitHub からチェックアウトした PyG リポジトリのルートフォルダから実行すること．
