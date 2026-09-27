from typing import Dict, Tuple, List

import torch
import torch.nn as nn
import torch.nn.functional as F

from torch_geometric.data import HeteroData
from torch_geometric.nn import GCNConv, GATConv
from torch_geometric.nn import MessagePassing


Nodetype = str
Edgetype = Tuple[str, str, str]



class HGTConv(MessagePassing):
    """HeteroGraphTransformer の myHGT 版。

    - HeteroConv の代わりに GraphConv を使用する。
    - ノードタイプごとに異なる MLP を持つ。
    - エッジタイプごとに異なる MLP を持つ。
    """

    def __init__(
        self,
        hidden_dim: int,
        edge_types: List[Edgetype],
        num_types: int,
        head_num: int,
    ) -> None:
        super().__init__(aggr="add")
        self.num_types = num_types

        assert hidden_dim % head_num == 0
        hidden_dim = hidden_dim // head_num

        self.k_linearList = nn.ModuleList()
        self.q_linearList = nn.ModuleList()
        self.v_linearList = nn.ModuleList()
        self.attn_weights = nn.ModuleList()

        for i in range(len(edge_types)):
            self.k_linearList.append(nn.Linear(hidden_dim, hidden_dim))
            self.q_linearList.append(nn.Linear(hidden_dim, hidden_dim))
            self.v_linearList.append(nn.Linear(hidden_dim, hidden_dim))

    def forward(self, edge_index, ) -> None:
        self.propagate(edge_index=edge_index)

    def message(self):
        pass

    def update(self, aggr_out):
        pass