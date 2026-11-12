import torch
from torch.nn import Linear, Parameter, ModuleList, Module, Dropout
import torch.nn.functional as F
from torch_geometric.nn import MessagePassing
from torch_geometric.utils import add_self_loops, degree, softmax
from torch_geometric.nn.inits import glorot
from typing import List

import scripts.datap.graph.const as c

NODE_TYPES:List[str] = ['stocks', 'statements', 'mktIdx', 'future']
EDGE_TYPES:List[str] = ['corr', 'made_up_Mkt', 'made_up_topix', 'made_up_s33', 'made_up_s17', 'recent_report', 'index_future']

class MarketHGTConv(MessagePassing):
    def __init__(self, in_hid:int, out_hid:int, num_head:int, dropout:float):
        super().__init__(aggr='add', node_dim=0)  # "Add" aggregation.

        self.in_hid = in_hid
        self.out_hid = out_hid
        self.num_head = num_head
        self.d_k = out_hid // num_head
        self.dropout = dropout

        self.q_linears = ModuleList([Linear(in_hid, out_hid) for _ in range(num_head)])
        self.k_linears = ModuleList([Linear(in_hid, out_hid) for _ in range(num_head)])
        self.v_linears = ModuleList([Linear(in_hid, out_hid) for _ in range(num_head)])
        self.a_linears = ModuleList([Linear(out_hid, out_hid) for _ in range(num_head)])

        self.W_att = Parameter(torch.Tensor(len(EDGE_TYPES), num_head, self.d_k, self.d_k))
        self.W_msg = Parameter(torch.Tensor(len(EDGE_TYPES), num_head, self.d_k, self.d_k))

        self.rel_pri = Parameter(torch.ones(len(EDGE_TYPES), num_head))

        self.drop = Dropout(self.dropout)
        self.skip = Parameter(torch.ones(len(NODE_TYPES)))

        glorot(self.W_att)
        glorot(self.W_msg)

    
    def forward(self, x, edge_index, ntIDs, etIDs):
        # x has shape [N, in_hid]
        return self.propagate(edge_index, x=x, node_type=ntIDs, etIDs=etIDs)

    def message(self, edge_index_i: torch.Tensor, x_i: torch.Tensor, x_j: torch.Tensor, node_type_i: torch.Tensor, node_type_j: torch.Tensor, etIDs: torch.Tensor):
        # x_j has shape [E, in_hid]
        # i : center node
        # j : neighbor node

        device = x_i.device

        out = torch.zeros(x_i.size(0), self.out_hid).to(device)

        res_att = torch.zeros(x_i.size(0), self.num_head).to(device)
        res_msg = torch.zeros(x_i.size(0), self.num_head, self.d_k).to(device)

        for i, j, r in c.HETERO_EDGE_UNIT_ID:
            edge_idx = (node_type_i == i) & (node_type_j == j) & (etIDs == r)

            if sum(edge_idx) == 0: continue

            target_x_i = x_i[edge_idx]
            source_x_j = x_j[edge_idx]

            Q_h: torch.Tensor = self.q_linears[i](target_x_i).view(-1, self.num_head, self.d_k)
            K_h: torch.Tensor = self.k_linears[j](source_x_j).view(-1, self.num_head, self.d_k)
            V_h: torch.Tensor = self.v_linears[j](source_x_j).view(-1, self.num_head, self.d_k)

            V_h = torch.bmm(V_h.transpose(0, 1), self.W_msg[r]).transpose(0, 1)
            msg = (V_h.contiguous()) #.view(-1, self.out_hid)

            K_h = torch.bmm(K_h.transpose(0, 1), self.W_att[r]).transpose(0, 1)
            att_head: torch.Tensor = (K_h * Q_h).sum(-1) * self.rel_pri[r]/self.d_k**0.5
            att = softmax(att_head, edge_index_i[edge_idx])

            res_att[edge_idx] = att
            res_msg[edge_idx] = msg

        out = res_msg * res_att.view(-1, self.num_head, 1)
        del res_att, res_msg
        return out.view(-1, self.out_hid)

    def update(self, aggr_out, node_type, x):
        aggr_out = F.gelu(aggr_out)
        aggr_res = torch.zeros(x.size(0), self.out_hid, device=x.device)

        for i in c.HETERO_NODE_ID.values():
            target_idx = (node_type == i)
            trans_out = self.drop(self.a_linears[i](aggr_out[target_idx]))

            alpha = F.sigmoid(self.skip[i])

            aggr_res[target_idx] = alpha * trans_out + (1 - alpha) * x[target_idx]

        return aggr_res


class GNNModel(Module):
    def __init__(self, in_hid:int=128, out_hid:int=128, num_head:int=4, num_layers:int=2, dropout:float=0.1):
        super().__init__()
        self.layers = ModuleList([MarketHGTConv(in_hid, out_hid, num_head, dropout) for _ in range(num_layers)])

    def forward(self, x, edge_index, node_type, edge_type):
        for layer in self.layers:
            x = layer(x, edge_index, node_type, edge_type)
        return x