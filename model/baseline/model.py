"""最も単純なベースライン GNN モデル。

`scripts/datap/graph/data_pipeline.py` が構築する HeteroData
（stock / statement / option / future の4ノードタイプ、各ノードタイプごとに
cont（連続値）/ cat（カテゴリ）/ date（日付経過日数）の3種の特徴量を持つ）
を入力とし、

  1. ノードタイプごとに NodeEncoder で共通の hidden_dim に写像
  2. HeteroConv({edge_type: GraphConv(...)}) を num_layers 回積み重ねてメッセージパッシング
  3. stock ノードの表現を2値分類ヘッドに通す（翌週リターン符号の予測）

という最小構成で作られている。相関エッジ（stock/option/future の corr 関係）は
edge_weight が最も重要な情報になるため、edge_weight を扱える GraphConv を採用する。
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.data import HeteroData
from torch_geometric.nn import GraphConv, HeteroConv

NodeType = str
EdgeType = Tuple[str, str, str]


class NodeEncoder(nn.Module):
    """ノードタイプ1種類分の cont/cat/date 特徴量を hidden_dim の1本のベクトルに写像する。"""

    def __init__(
        self,
        cont_dim: int,
        cat_vocab_sizes: List[int],
        date_dim: int,
        hidden_dim: int,
        cat_embed_dim: int = 8,
    ) -> None:
        super().__init__()
        # cont/date は生の値のスケールが列ごとに大きく異なる（例: log株価 vs 経過日数）ため、
        # LayerNorm で正規化してから Linear に通す。NeighborLoader のミニバッチはノードタイプ
        # ごとのサンプル数が数個〜1個になることもあり得るため、バッチ統計に依存する BatchNorm
        # ではなくサンプル単位で完結する LayerNorm を使う。
        self.cont_norm = nn.LayerNorm(cont_dim)
        self.cont_lin = nn.Linear(cont_dim, hidden_dim)

        self.cat_embeds = nn.ModuleList([nn.Embedding(v, cat_embed_dim) for v in cat_vocab_sizes])
        self.cat_lin = nn.Linear(cat_embed_dim * len(cat_vocab_sizes), hidden_dim)

        # date 列を持つのは現状 statement のみ（他タイプは date_dim=0 で埋め込まない）
        if date_dim > 0:
            self.date_norm = nn.LayerNorm(date_dim)
            self.date_lin = nn.Linear(date_dim, hidden_dim)
        else:
            self.date_norm = None
            self.date_lin = None

    def forward(self, x: torch.Tensor, cat_x: torch.Tensor, date_x: torch.Tensor) -> torch.Tensor:
        # 一部の列（例: stock の r_i は上場直後の週で前週終値が存在せず NaN）は欠損しうる。
        # LayerNorm は1つでも NaN が混じると行全体が NaN に伝播するため、事前に 0 埋めする。
        out = self.cont_lin(self.cont_norm(torch.nan_to_num(x)))

        cat_embed = torch.cat([emb(cat_x[:, i]) for i, emb in enumerate(self.cat_embeds)], dim=-1)
        out = out + self.cat_lin(cat_embed)

        if self.date_lin is not None:
            assert isinstance(self.date_norm, nn.LayerNorm)
            out = out + self.date_lin(self.date_norm(torch.nan_to_num(date_x)))

        return F.relu(out)


class BaselineHeteroGNN(nn.Module):
    """HeteroConv + GraphConv を積み重ねた最小構成のヘテログラフ GNN。"""

    def __init__(
        self,
        node_feat_dims: Dict[NodeType, Dict[str, object]],
        edge_types: List[EdgeType],
        hidden_dim: int = 64,
        num_layers: int = 2,
        num_classes: int = 2,
        dropout: float = 0.2,
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
        self.convs = nn.ModuleList(
            [
                HeteroConv(
                    {edge_type: GraphConv(hidden_dim, hidden_dim, aggr="mean") for edge_type in edge_types},
                    aggr="sum",
                )
                for _ in range(num_layers)
            ]
        )
        self.dropout = dropout
        self.classifier = nn.Linear(hidden_dim, num_classes)

    def forward(self, batch: HeteroData) -> torch.Tensor:
        """`batch` は NeighborLoader が返す HeteroData ミニバッチ。stock 全ノードのロジットを返す。"""
        h_dict = {
            node_type: encoder(batch[node_type].x, batch[node_type].cat_x, batch[node_type].date_x)
            for node_type, encoder in self.encoders.items()
        }
        edge_index_dict  = {et: batch[et].edge_index  for et in batch.edge_types}
        edge_weight_dict = {et: batch[et].edge_weight for et in batch.edge_types}

        for conv in self.convs:
            out_dict = conv(h_dict, edge_index_dict, edge_weight_dict=edge_weight_dict)
            h_dict = {
                node_type: (
                    F.dropout(F.relu(out_dict[node_type]), p=self.dropout, training=self.training)
                    if node_type in out_dict
                    else h_dict[node_type]
                )
                for node_type in h_dict
            }

        return self.classifier(h_dict["stock"])
