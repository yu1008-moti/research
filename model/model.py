import model.conv as conv
import scripts.datap.graph.const as c

from torch import nn
import torch
from typing import Dict, List, Tuple
from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence

NUM_LABELS = c.NUM_LABELS  # Assuming 3 classes for classification
DEVICE = c.DEVICE

class Classifier(nn.Module):
    def __init__(self, in_hid:int):
        super().__init__()
        self.classifier = nn.Linear(in_hid, NUM_LABELS)  # Assuming 3 classes for classification

    def forward(self, x, target):
        x = x[target]
        return self.classifier(x)

class myGRU(nn.Module):
    def __init__(self, hidden_size: int, node_type_cfg: Dict[str, int], bidirectional: bool = False):
        super().__init__()
        self.node_type_cfg = node_type_cfg
        self.hidden_size = hidden_size
        self.bidirectional = bidirectional
        
        self.linear_layers = nn.ModuleDict({
            node_type: nn.Linear(in_dim*2, hidden_size) 
            for node_type, in_dim in node_type_cfg.items()
        })

        self.GRUs = nn.ModuleList([
            nn.GRU(
                in_dim,
                self.hidden_size,
                batch_first=True,
                bidirectional=bidirectional
            ) 
            for in_dim in self.node_type_cfg.values()
        ])

    def forward(self, x, seq_len, x_node_types):

        # assert len(x) == x_node_types.size(0), "Mismatch in number of nodes and node types"

        emb = torch.zeros(len(x_node_types), self.hidden_size, device=DEVICE)
        # x_node_types = torch.zeros(len(x_node_types), dtype=torch.long, device=DEVICE)  # Placeholder for node types
        
        idx_st = 0
        idx_end = 0

        for node_type in range(len(self.node_type_cfg)):
            # empty = seq_len[node_type] == 0
            lens  = seq_len[node_type].clamp(min=1)
            packed = pack_padded_sequence(
                x[node_type], lens, batch_first=True, enforce_sorted=False
            ).to(DEVICE)
            idx_end += len(packed.sorted_indices) 
            o_n, h_n = self.GRUs[node_type](packed)
            if self.bidirectional:
                h = torch.cat([h_n[-2], h_n[-1]], dim=-1)
                h = self.linear_layers[node_type](h)  # Apply linear layer to reduce dimension
            else:
                h = h_n[-1]
            emb[idx_st:idx_end] = h
            idx_st = idx_end

        return emb
            

class MarketHGTModel(nn.Module):#
    def __init__(
            self, in_hid:int, out_hid:int, num_head:int, num_layers:int, dropout:float, node_type_cfg: Dict[str, int], bidirectional: bool = False):
        super().__init__()
        # 
        self.gru = myGRU(out_hid, node_type_cfg, bidirectional)
        self.hgt_conv = conv.GNNModel(in_hid, out_hid, num_head, num_layers, dropout)
        self.classifier = Classifier(out_hid)

    def forward(self, x, seq_len, edge_index, node_type_i, node_type_j, edge_type_ij, target):
        # Pass through GRU
        # forward(self, x, seq_len, x_node_types):
        x = self.gru(x, seq_len, node_type_i)  # Assuming node_type_i represents the node types for GRU
        # Pass through HGTConv
        x = self.hgt_conv(x, edge_index, node_type_i, node_type_j, edge_type_ij)
        
        # Pass through classifier
        return self.classifier(x, target)  # Assuming classifier takes x and target for loss computation