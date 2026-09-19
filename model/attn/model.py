"""GraphGPS 風のグローバル注意（`torch_geometric.nn.attention.PerformerAttention`）を
`model/baseline` のローカル HeteroConv メッセージパッシングに追加した GNN。

## 提案の経緯・妥当性検討

`model/baseline` は `HeteroConv(GraphConv)` のみで、各 stock ノードは近傍サンプリング
（`NeighborLoader`、既定 2 hop）で辿り着ける範囲でしか他ノードの情報を集約できない。
一方 `stock-corr-stock` エッジは `|corr|>0.7` を満たすペアだけに絞られており
（`scripts/datap/graph/capm_corr.py`）、閾値未満だが弱く関連する銘柄間の相互作用は
そもそもグラフに現れない。GraphGPS 論文（Rampášek et al., 2022）が提案する
「ローカル MPNN + グローバル注意のハイブリッド」を踏襲し、stock ノードに限り
週（`time_id`）単位のグローバル注意を追加すれば、この閾値外の関係も学習可能になる。

素の softmax attention は同じ週に含まれる stock ノード数 N に対して O(N^2) だが、
`stock-derivative-future` エッジが hub 構造（1〜2本の指数先物に全 is_target 銘柄が
接続、次数が数百〜数千）を持つ関係で `NeighborLoader` のミニバッチにも stock ノードが
数百〜数千件含まれ得る（`model/README.md` 参照）。`PerformerAttention`
（Choromanski et al., 2020, FAVOR+ による線形時間近似）はこれを O(N) に抑えられるため、
素の `nn.MultiheadAttention` より本用途に適している。

結論: 妥当と判断し実装した。ただし以下は意図的なスコープ限定・既知の制約:

- 注意は **stock ノードのみ**に適用する（予測対象であり、かつ `option`（930万行規模）
  等にまで広げると計算コストが無視できなくなるため）。
- `to_dense_batch` は「同じグループの行が連続している」ことを前提にした実装になっている
  （内部で累積和ベースにローカル位置を逆算するため、グループが飛び飛びだと衝突する）。
  `NeighborLoader` はノードを `time_id` 順に並べてくれないため、
  `_grouped_performer_attention()` で明示的に安定ソートしてから戻している。
- ミニバッチ内でグループ化するため、あるバッチに含まれる同一 `time_id` の stock ノードは
  近傍サンプリングでその週にたまたま含まれたものだけであり、その週の全銘柄横断
  （真のクロスセクション）ではない。真のクロスセクション注意にしたい場合は
  `time_id` を種ノード側で揃えたサンプリング戦略に変更する必要がある（未実装）。
- `PerformerAttention` の乱択直交射影行列は `_reset_parameters()` 時に1回だけ描画される
  （論文が推奨する定期的な re-draw はここでは行っていない）。
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.data import HeteroData
from torch_geometric.nn import GraphConv, HeteroConv
from torch_geometric.nn.attention import PerformerAttention
from torch_geometric.utils import to_dense_batch

from model.baseline.model import NodeEncoder

NodeType = str
EdgeType = Tuple[str, str, str]


def _grouped_performer_attention(
    x: torch.Tensor, group_ids: torch.Tensor, attn: PerformerAttention
) -> torch.Tensor:
    """`group_ids`（ここでは `time_id`）が同じノード同士だけで注意を計算する。

    `to_dense_batch` は batch ベクトルが「グループ順に並んでいる」ことを前提にしている
    （ドキュメントに ``Must be ordered`` と明記。内部では累積和からグループ内の
    ローカル位置を逆算しており、同一グループの行が飛び飛びだと位置が衝突・破損する）。
    `NeighborLoader` のミニバッチはこの順序を保証しないため、ここで一度安定ソートしてから
    `to_dense_batch` に渡し、計算後に元の並びへ戻す。
    """
    _, inverse = torch.unique(group_ids, return_inverse=True)
    perm = torch.argsort(inverse, stable=True)
    inv_perm = torch.empty_like(perm)
    inv_perm[perm] = torch.arange(perm.numel(), device=perm.device)

    dense_x, mask = to_dense_batch(x[perm], inverse[perm])
    out = attn(dense_x, mask=mask)
    out = out[mask]
    return out[inv_perm]


class StockGPSBlock(nn.Module):
    """全ノードタイプの HeteroConv ローカル更新 + stock ノードのみの週単位グローバル注意。

    GraphGPS 論文の `GPSConv`（`torch_geometric.nn.conv.gps_conv.GPSConv`）の
    「local + global を合算し、残差接続 + LayerNorm + FFN でまとめる」という構成を、
    単一エッジタイプ・単一ノードタイプ前提の `GPSConv` から本リポジトリのヘテロググラフ
    （複数ノードタイプ・複数エッジタイプ、`edge_weight` 付き）向けに書き直したもの。
    """

    def __init__(
        self,
        hidden_dim: int,
        edge_types: List[EdgeType],
        heads: int = 4,
        head_channels: int | None = None,
        dropout: float = 0.2,
    ) -> None:
        super().__init__()
        if head_channels is None:
            head_channels = max(hidden_dim // heads, 1)

        self.conv = HeteroConv(
            {edge_type: GraphConv(hidden_dim, hidden_dim, aggr="mean") for edge_type in edge_types},
            aggr="sum",
        )
        self.attn = PerformerAttention(
            channels=hidden_dim, heads=heads, head_channels=head_channels, dropout=dropout
        )
        self.norm_local = nn.LayerNorm(hidden_dim)
        self.norm_attn = nn.LayerNorm(hidden_dim)
        self.norm_out = nn.LayerNorm(hidden_dim)
        self.mlp = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim * 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.Dropout(dropout),
        )
        self.dropout = dropout

    def forward(
        self,
        h_dict: Dict[NodeType, torch.Tensor],
        edge_index_dict: Dict[EdgeType, torch.Tensor],
        edge_weight_dict: Dict[EdgeType, torch.Tensor],
        stock_time_id: torch.Tensor,
    ) -> Dict[NodeType, torch.Tensor]:
        out_dict = self.conv(h_dict, edge_index_dict, edge_weight_dict=edge_weight_dict)

        new_h_dict = {}
        for node_type, h in h_dict.items():
            if node_type not in out_dict:
                new_h_dict[node_type] = h
                continue
            if node_type != "stock":
                # stock 以外は baseline と同じくローカル更新のみ（残差なし）。
                new_h_dict[node_type] = F.dropout(F.relu(out_dict[node_type]), p=self.dropout, training=self.training)
                continue

            local = F.dropout(out_dict[node_type], p=self.dropout, training=self.training)
            local = self.norm_local(local + h)

            global_ = _grouped_performer_attention(h, stock_time_id, self.attn)
            global_ = F.dropout(global_, p=self.dropout, training=self.training)
            global_ = self.norm_attn(global_ + h)

            stock_h = local + global_
            stock_h = self.norm_out(stock_h + self.mlp(stock_h))
            new_h_dict[node_type] = stock_h

        return new_h_dict


class AttnHeteroGNN(nn.Module):
    """`StockGPSBlock` を積み重ねたヘテログラフ GNN（`model.baseline.BaselineHeteroGNN` の attention 版）。"""

    def __init__(
        self,
        node_feat_dims: Dict[NodeType, Dict[str, object]],
        edge_types: List[EdgeType],
        hidden_dim: int = 64,
        num_layers: int = 2,
        num_classes: int = 2,
        dropout: float = 0.2,
        attn_heads: int = 4,
        attn_head_channels: int | None = None,
    ) -> None:
        super().__init__()
        self.encoders = nn.ModuleDict(
            {
                node_type: NodeEncoder(
                    cont_dim=dims["cont"]       if isinstance(dims["cont"], int) else 0,
                    cat_vocab_sizes=dims["cat"] if isinstance(dims["cat"], list) else [],
                    date_dim=dims["date"]       if isinstance(dims["date"], int) else 0,
                    hidden_dim=hidden_dim,
                )
                for node_type, dims in node_feat_dims.items()
            }
        )
        self.blocks = nn.ModuleList(
            [
                StockGPSBlock(
                    hidden_dim,
                    edge_types,
                    heads=attn_heads,
                    head_channels=attn_head_channels,
                    dropout=dropout,
                )
                for _ in range(num_layers)
            ]
        )
        self.classifier = nn.Linear(hidden_dim, num_classes)

    def forward(self, batch: HeteroData) -> torch.Tensor:
        """`batch` は NeighborLoader が返す HeteroData ミニバッチ。stock 全ノードのロジットを返す。"""
        h_dict = {
            node_type: encoder(batch[node_type].x, batch[node_type].cat_x, batch[node_type].date_x)
            for node_type, encoder in self.encoders.items()
        }
        edge_index_dict  = {et: batch[et].edge_index  for et in batch.edge_types}
        edge_weight_dict = {et: batch[et].edge_weight for et in batch.edge_types}
        stock_time_id = batch["stock"].time_id

        for block in self.blocks:
            h_dict = block(h_dict, edge_index_dict, edge_weight_dict, stock_time_id)

        return self.classifier(h_dict["stock"])
