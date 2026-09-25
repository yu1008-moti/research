# Graph Transformer

- [Graph Transformer](#graph-transformer)
  - [Transformers on Graphs](#transformers-on-graphs)
    - [Attention](#attention)
    - [Positional and Structural Encodings](#positional-and-structural-encodings)
  - [GPS Layer and GraphGPS Model](#gps-layer-and-graphgps-model)
    - [Local MPNN](#local-mpnn)
    - [Global Attention](#global-attention)
    - [Combine local and global outputs](#combine-local-and-global-outputs)
  - [Train GraphGPS on graph-structured data](#train-graphgps-on-graph-structured-data)
    - [Load dataset](#load-dataset)
    - [Define model](#define-model)
    - [Train and evaluate](#train-and-evaluate)

---

[Transformer](https://arxiv.org/abs/1706.03762) は，[自然言語処理](https://arxiv.org/abs/1810.04805) や [コンピュータビジョン](https://arxiv.org/abs/2010.11929) において効果的なアーキテクチャである．
近年，Transformer をグラフと組み合わせるいくつかの応用（[Grover](https://arxiv.org/abs/2007.02835)，[GraphGPS](https://arxiv.org/abs/2205.12454) など）が登場している．
このチュートリアルでは，PyG を用いて Graph Transformer モデルを構築する方法を紹介する．このトピックについてより深く学びたい場合は，[こちらのウェビナー](https://youtu.be/wAYryx3GjLw?si=2vB7imfenP5tUvqd) を参照してほしい．

> **Note**
>
> 完全なサンプルコードは[こちら](https://github.com/pyg-team/pytorch_geometric/blob/master/examples/graph_gps.py)からダウンロードできる．

## Transformers on Graphs

Graph Transformer と比較して，MPNN にはいくつかの欠点がある．(1) WL テスト：1次の MPNN は表現力に限界がある．(2) Over-smoothing（過平滑化）：GNN の層数を増やすにつれて，特徴量が同じ値に収束していく傾向がある．(3) Over-squashing（過圧縮）：多数の近傍からのメッセージを1つのベクトルへ集約しようとする際に情報が失われる．(4) 長距離依存関係を捉えられない．

グラフ全体を Transformer へ入力することにも，いくつかの長所と短所がある．

**長所（Pros）**

- 計算グラフの構造が，入力グラフの構造から分離されている．
- すべてのノードが互いに接続されているため，長距離の接続を扱える．

**短所（Cons）**

- GNN がグラフ上でうまく機能する要因である，帰納バイアス（inductive bias）が失われる．特に，エッジが関連性・近接性を表すグラフにおいて顕著である．
- 言語の入力は系列的（sequential）であるが，グラフはノードの順序に対して置換不変（permutation invariant）である．
- ノード数に対して2乗の計算量 $O(N^2)$ となるのに対し，メッセージパッシング GNN はエッジ数に対して線形の計算量 $O(E)$ である．グラフはしばしば疎（sparse）であり，$N \approx E$ である．

### Attention

$$Q = XW_Q, K = XW_K, V = XW_V$$

$$Attention(Q, K, V) = softmax(\frac{QK^T}{\sqrt{d_k}})V$$

Transformer において，attention はマルチヘッドにすることができ，複数の attention 重みから構成される．

### Positional and Structural Encodings

PE/SE を，その局所性（locality）に基づいて (1) Local，(2) Global，(3) Relative の3つのカテゴリに整理した．
Positional encodings（PE，位置エンコーディング）は，グラフ内におけるあるノードの空間的な位置についての情報を与える．グラフあるいは部分グラフ内で2つのノードが互いに近い場合，それらの PE も近い値になるべきである．
Structure encodings（SE，構造エンコーディング）は，グラフや部分グラフの構造の埋め込みを与え，GNN の表現力と汎化性能の向上に役立つ．
2つのノードが類似した部分グラフを共有している場合，あるいは2つのグラフが類似している場合，それらの SE も近い値になるべきである．

| Encoding type | Positional encodings (PE) | Structure encodings (SE) |
| --- | --- | --- |
| Local (node) | (1) クラスタ中心までの距離；(2) mステップのランダムウォークにおける非対角成分の総和． | (1) ノード次数；(2) ランダムウォークの対角成分；(3) 部分構造（三角形，環など）の列挙． |
| Global (node) | (1) A/L あるいは距離行列の固有ベクトル；(2) グラフの重心までの距離；(3) 各ノードに対する一意な ID． | (1) A/L の固有値；(2) グラフの直径，内周（girth），次数など． |
| Relative (edge) | (1) Heat Kernels，Random Walks，Graph geodesic 等からのペアワイズ距離；(2) 固有ベクトルの勾配 | (1) 任意の Local SE の勾配；(2) 部分構造列挙の勾配 |

## GPS Layer and GraphGPS Model

まず，局所的な MPNN と大域的な Transformer を組み合わせ，その後に2層 MLP とスキップ接続を続けた GPS レイヤーを紹介する．
局所的な MPNN は，Transformer では実現が難しい，あるいはコストの高い局所性バイアス（locality bias）を提供できる．
さらに，エッジの特徴を更新し，ノード特徴へエンコードすることもできる（[GatedGCN](https://arxiv.org/abs/1711.07553)，[GINE](https://arxiv.org/abs/1905.12265)）．
Transformer は位置エンコーディングと構造エンコーディングを利用できる．エッジ特徴を考慮する必要がないため，[Performer](https://arxiv.org/abs/2009.14794) や [BigBird](https://arxiv.org/abs/2007.14062) のような，既存の線形 Transformer アーキテクチャを用いて，時間計算量を $O(N^2)$ から $O(N + E)$ へ削減できる．

> **Warning**
>
> [BigBird](https://arxiv.org/abs/2007.14062) は現時点ではサポートされておらず，将来的に追加される予定である．

[](../_images/graphgps_layer.png)

各レイヤーの更新関数は，以下の式で表される．

### Local MPNN

$$\hat{X}_M^{l + 1}, E^{l + 1} = MPNN_e^l(X^l, E^l, A)$$

$$X_M^{l + 1} = BatchNorm(Dropout(\hat{X}_M^{l + 1}) + X^l)$$

```python
h = self.conv(x, edge_index, **kwargs)
h = F.dropout(h, p=self.dropout, training=self.training)
h = h + x
if self.norm1 is not None:
    if self.norm_with_batch:
        h = self.norm1(h, batch=batch)
    else:
        h = self.norm1(h)
hs.append(h)
```

### Global Attention

$$\hat{X}_T^{l + 1} = GlobalAttn^l(X^l)$$

$$X_T^{l + 1} = BatchNorm(Dropout(\hat{X}_T^{l + 1}) + X^l)$$

```python
h, mask = to_dense_batch(x, batch)

if isinstance(self.attn, torch.nn.MultiheadAttention):
    h, _ = self.attn(h, h, h, key_padding_mask=~mask,
                    need_weights=False)
elif isinstance(self.attn, PerformerAttention):
    h = self.attn(h, mask=mask)

h = h[mask]
h = F.dropout(h, p=self.dropout, training=self.training)
h = h + x  # Residual connection.
if self.norm2 is not None:
    if self.norm_with_batch:
        h = self.norm2(h, batch=batch)
    else:
        h = self.norm2(h)
hs.append(h)
```

### Combine local and global outputs

$$X^{l + 1} = MLP^l(X_M^{l + 1} + X_T^{l + 1})$$

```python
out = sum(hs)

out = out + self.mlp(out)
if self.norm3 is not None:
    if self.norm_with_batch:
        out = self.norm3(out, batch=batch)
    else:
        out = self.norm3(out)
```

次に，GraphGPS アーキテクチャを紹介する．[GraphGPS](https://arxiv.org/abs/2205.12454) と [GraphTrans](https://arxiv.org/abs/2201.08821) の違いは，MPNN と Transformer の組み合わせ方にある．
GraphTrans では，Transformer の前に数層の MPNN が配置されており，over-smoothing，over-squashing，WL テストに対する低い表現力といった問題によって制約を受ける可能性がある．
これらの層は，初期段階で一部の情報を取り返しのつかない形で失ってしまうことがある．GraphGPS の設計は，MPNN + Transformer のハイブリッドを積み重ねる構成になっており，完全連結性（full-connectivity）を通じてグラフ全体に情報を広げることで，局所的な表現力のボトルネックを解消している．

## Train GraphGPS on graph-structured data

この部分では，[`ZINC`](../generated/torch_geometric.datasets.ZINC.html#torch_geometric.datasets.ZINC) データセットを用いて `GPSConv` GNN モデルを学習する方法を紹介する．

### Load dataset

```python
transform = T.AddRandomWalkPE(walk_length=20, attr_name='pe')
train_dataset = ZINC(path, subset=True, split='train', pre_transform=transform)
val_dataset = ZINC(path, subset=True, split='val', pre_transform=transform)
test_dataset = ZINC(path, subset=True, split='test', pre_transform=transform)

train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
val_loader = DataLoader(val_dataset, batch_size=64)
test_loader = DataLoader(test_dataset, batch_size=64)
```

### Define model

```python
class RedrawProjection:
    def __init__(self, model: torch.nn.Module,
                redraw_interval: Optional[int] = None):
        self.model = model
        self.redraw_interval = redraw_interval
        self.num_last_redraw = 0

    def redraw_projections(self):
        if not self.model.training or self.redraw_interval is None:
            return
        if self.num_last_redraw >= self.redraw_interval:
            fast_attentions = [
                module for module in self.model.modules()
                if isinstance(module, PerformerAttention)
            ]
            for fast_attention in fast_attentions:
                fast_attention.redraw_projection_matrix()
            self.num_last_redraw = 0
            return
        self.num_last_redraw += 1

class GPS(torch.nn.Module):
    def __init__(self, channels: int, pe_dim: int, num_layers: int,
                attn_type: str, attn_kwargs: Dict[str, Any]):
        super().__init__()

        self.node_emb = Embedding(28, channels - pe_dim)
        self.pe_lin = Linear(20, pe_dim)
        self.pe_norm = BatchNorm1d(20)
        self.edge_emb = Embedding(4, channels)

        self.convs = ModuleList()
        for _ in range(num_layers):
            nn = Sequential(
                Linear(channels, channels),
                ReLU(),
                Linear(channels, channels),
            )
            conv = GPSConv(channels, GINEConv(nn), heads=4,
                        attn_type=attn_type, attn_kwargs=attn_kwargs)
            self.convs.append(conv)

        self.mlp = Sequential(
            Linear(channels, channels // 2),
            ReLU(),
            Linear(channels // 2, channels // 4),
            ReLU(),
            Linear(channels // 4, 1),
        )
        self.redraw_projection = RedrawProjection(
            self.convs,
            redraw_interval=1000 if attn_type == 'performer' else None)

    def forward(self, x, pe, edge_index, edge_attr, batch):
        x_pe = self.pe_norm(pe)
        x = torch.cat((self.node_emb(x.squeeze(-1)), self.pe_lin(x_pe)), 1)
        edge_attr = self.edge_emb(edge_attr)

        for conv in self.convs:
            x = conv(x, edge_index, batch, edge_attr=edge_attr)
        x = global_add_pool(x, batch)
        return self.mlp(x)
```

### Train and evaluate

```python
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
attn_kwargs = {'dropout': 0.5}
model = GPS(channels=64, pe_dim=8, num_layers=10, attn_type=args.attn_type,
            attn_kwargs=attn_kwargs).to(device)
optimizer = torch.optim.Adam(model.parameters(), lr=0.001, weight_decay=1e-5)
scheduler = ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=20,
                            min_lr=0.00001)

def train():
    model.train()

    total_loss = 0
    for data in train_loader:
        data = data.to(device)
        optimizer.zero_grad()
        model.redraw_projection.redraw_projections()
        out = model(data.x, data.pe, data.edge_index, data.edge_attr,
                    data.batch)
        loss = (out.squeeze() - data.y).abs().mean()
        loss.backward()
        total_loss += loss.item() * data.num_graphs
        optimizer.step()
    return total_loss / len(train_loader.dataset)

@torch.no_grad()
def test(loader):
    model.eval()

    total_error = 0
    for data in loader:
        data = data.to(device)
        out = model(data.x, data.pe, data.edge_index, data.edge_attr,
                    data.batch)
        total_error += (out.squeeze() - data.y).abs().sum().item()
    return total_error / len(loader.dataset)

for epoch in range(1, 101):
    loss = train()
    val_mae = test(val_loader)
    test_mae = test(test_loader)
    scheduler.step(val_mae)
    print(f'Epoch: {epoch:02d}, Loss: {loss:.4f}, Val: {val_mae:.4f}, '
        f'Test: {test_mae:.4f}')
```

```
Epoch: 01, Loss: 0.7216, Val: 0.5316, Test: 0.5454
Epoch: 02, Loss: 0.5519, Val: 0.5895, Test: 0.6288
Epoch: 03, Loss: 0.5009, Val: 0.5029, Test: 0.4924
Epoch: 04, Loss: 0.4751, Val: 0.4801, Test: 0.4786
Epoch: 05, Loss: 0.4363, Val: 0.4438, Test: 0.4352
Epoch: 06, Loss: 0.4276, Val: 0.4931, Test: 0.4994
Epoch: 07, Loss: 0.3956, Val: 0.3502, Test: 0.3439
Epoch: 08, Loss: 0.4021, Val: 0.3143, Test: 0.3296
Epoch: 09, Loss: 0.3761, Val: 0.4012, Test: 0.3858
Epoch: 10, Loss: 0.3739, Val: 0.3343, Test: 0.3032
Epoch: 11, Loss: 0.3532, Val: 0.3679, Test: 0.3334
Epoch: 12, Loss: 0.3683, Val: 0.3094, Test: 0.2754
Epoch: 13, Loss: 0.3457, Val: 0.4007, Test: 0.4023
Epoch: 14, Loss: 0.3460, Val: 0.3986, Test: 0.3589
Epoch: 15, Loss: 0.3369, Val: 0.3478, Test: 0.3124
Epoch: 16, Loss: 0.3222, Val: 0.3043, Test: 0.2651
Epoch: 17, Loss: 0.3190, Val: 0.4496, Test: 0.4070
Epoch: 18, Loss: 0.3317, Val: 0.3803, Test: 0.3450
Epoch: 19, Loss: 0.3179, Val: 0.2671, Test: 0.2408
Epoch: 20, Loss: 0.3143, Val: 0.4168, Test: 0.3901
Epoch: 21, Loss: 0.3238, Val: 0.3183, Test: 0.2926
Epoch: 22, Loss: 0.3132, Val: 0.9534, Test: 1.0879
Epoch: 23, Loss: 0.3088, Val: 0.3705, Test: 0.3360
Epoch: 24, Loss: 0.3032, Val: 0.3051, Test: 0.2692
Epoch: 25, Loss: 0.2968, Val: 0.2829, Test: 0.2571
Epoch: 26, Loss: 0.2915, Val: 0.3145, Test: 0.2820
Epoch: 27, Loss: 0.2871, Val: 0.3127, Test: 0.2965
Epoch: 28, Loss: 0.2953, Val: 0.4415, Test: 0.4144
Epoch: 29, Loss: 0.2916, Val: 0.3118, Test: 0.2733
Epoch: 30, Loss: 0.3074, Val: 0.4497, Test: 0.4418
```
