# TorchScript Support

- [TorchScript Support](#torchscript-support)
  - [Converting GNN Models](#converting-gnn-models)
  - [Creating Jittable GNN Operators](#creating-jittable-gnn-operators)

---

TorchScript は，PyTorch のコードからシリアライズ可能かつ最適化可能なモデルを作成するための仕組みである．
TorchScript プログラムは，Python プロセス上で保存し，Python への依存がないプロセスへ読み込むことができる．
TorchScript に馴染みがない場合は，まず公式の [“Introduction to TorchScript”](https://pytorch.org/tutorials/beginner/Intro_to_TorchScript_tutorial.html) チュートリアルを読むことを推奨する．

## Converting GNN Models

> **Note**
> PyG 2.5（およびそれ以降）では，GNN レイヤーは特に変更を加えることなく `torch.jit.script()` と完全に互換性を持つようになった．
> それより前のバージョンの PyG を使用している場合は，まず [`jittable()`](../generated/torch_geometric.nn.conv.MessagePassing.html#torch_geometric.nn.conv.MessagePassing.jittable) を呼び出すことで，GNN レイヤーを「jittable」なインスタンスへ変換することを検討してほしい．

PyG モデルを TorchScript プログラムへ変換するのは簡単で，わずかなコード変更のみで済む．
次のモデルを考えてみよう．

```python
import torch
import torch.nn.functional as F
from torch_geometric.nn import GCNConv

class GNN(torch.nn.Module):
    def __init__(self, in_channels, out_channels):
        super().__init__()
        self.conv1 = GCNConv(in_channels, 64)
        self.conv2 = GCNConv(64, out_channels)

    def forward(self, x, edge_index):
        x = self.conv1(x, edge_index)
        x = F.relu(x)
        x = self.conv2(x, edge_index)
        return F.log_softmax(x, dim=1)

model = GNN(dataset.num_features, dataset.num_classes)
```

インスタンス化したモデルは，そのまま `torch.jit.script()` に渡すことができる．

```python
model = torch.jit.script(model)
```

PyG モデルを TorchScript プログラムへ変換するために必要な知識は，これで全てである．
ノード分類・グラフ分類のモデルについて TorchScript プログラムを取得する方法を示す，[node](https://github.com/pyg-team/pytorch_geometric/blob/master/examples/jit/gat.py) および [graph classification](https://github.com/pyg-team/pytorch_geometric/blob/master/examples/jit/gin.py) の JIT サンプルもあわせて参照してほしい．

## Creating Jittable GNN Operators

すべての PyG [`MessagePassing`](../generated/torch_geometric.nn.conv.MessagePassing.html#torch_geometric.nn.conv.MessagePassing) 演算子は，TorchScript プログラムへ変換可能であることがテストされている．
しかし，自作の GNN モジュールを `torch.jit.script()` と互換にしたい場合は，次の2点を考慮する必要がある．

1. 当然のことながら，型注釈を追加するなどして，`forward()` のコードが TorchScript コンパイラの要件を満たすように調整する必要がある場合がある．
2. [`propagate()`](../generated/torch_geometric.nn.conv.MessagePassing.html#torch_geometric.nn.conv.MessagePassing.propagate) 関数に渡す引数の型を，[`MessagePassing`](../generated/torch_geometric.nn.conv.MessagePassing.html#torch_geometric.nn.conv.MessagePassing) モジュールへ伝える必要がある．これは次の2通りの方法で実現できる．

   1. `propagate_type` という辞書の中で，伝播（propagate）引数の型を宣言する方法．

      ```python
      from typing import Optional
      from torch import Tensor
      from torch_geometric.nn import MessagePassing

      class MyConv(MessagePassing):
          propagate_type = {'x': Tensor, 'edge_weight': Optional[Tensor] }

          def forward(
              self,
              x: Tensor,
              edge_index: Tensor,
              edge_weight: Optional[Tensor] = None,
          ) -> Tensor:
              return self.propagate(edge_index, x=x, edge_weight=edge_weight)
      ```

   2. モジュール内のコメントとして，伝播引数の型を宣言する方法．

      ```python
      from typing import Optional
      from torch import Tensor
      from torch_geometric.nn import MessagePassing

      class MyConv(MessagePassing):
          def forward(
              self,
              x: Tensor,
              edge_index: Tensor,
              edge_weight: Optional[Tensor] = None,
          ) -> Tensor:
              # propagate_type: (x: Tensor, edge_weight: Optional[Tensor])
              return self.propagate(edge_index, x=x, edge_weight=edge_weight)
      ```

これらのいずれの方法も指定しなかった場合，[`MessagePassing`](../generated/torch_geometric.nn.conv.MessagePassing.html#torch_geometric.nn.conv.MessagePassing) モジュールは `propagate()` の引数の型を [`torch.Tensor`](https://docs.pytorch.org/docs/main/tensors.html#torch.Tensor) であると推論する（これは，型注釈のない引数に対して TorchScript がデフォルトで推論する型を模したものである）．
