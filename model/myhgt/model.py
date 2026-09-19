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
        head_num: int,
    ) -> None:
        super().__init__()

        assert hidden_dim % head_num == 0
        ith_head_dim = hidden_dim // head_num

        self.k_linear = nn.ModuleList()
        self.q_linear = nn.ModuleList()
        self.v_linear = nn.ModuleList()
        self.a_linear = nn.ModuleList()

        for _ in range(len(edge_types)):
            self.k_linear.append(nn.Linear(hidden_dim, ith_head_dim))
            self.q_linear.append(nn.Linear(hidden_dim, ith_head_dim))
            self.v_linear.append(nn.Linear(hidden_dim, ith_head_dim))
            self.a_linear.append(nn.Linear(ith_head_dim, hidden_dim))

        self.relation_pri = nn.Parameter(torch.ones(len(edge_types), head_num))

    def forward(self, edge_index, ) -> None:
        self.propagate(edge_index=edge_index)