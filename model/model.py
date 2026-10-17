import model.conv as conv
import scripts.datap.graph.const as c

from torch import nn
import torch
from typing import Dict, List, Tuple
from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence

NUM_LABELS = c.NUM_LABELS  # Assuming 3 classes for classification
DEVICE = c.DEVICE

class Classifier(nn.Module):
    def __init__(self, in_hid:int, ):
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

        assert x.size(0) == x_node_types.size(0), "Mismatch in number of nodes and node types"

        empty = seq_len == 0
        lens = seq_len.clamp(min=1).cpu()

        packed = pack_padded_sequence(x, lens, batch_first=True, enforce_sorted=False)

        embeddings = torch.zeros(x.size(0), self.hidden_size, device=DEVICE)

        for node_type in range(len(self.node_type_cfg)):
            idx = (x_node_types == node_type)
            x_node_type = packed[idx].unsqueeze(0)  # Add sequence dimension
            _, h_n = self.GRUs[node_type](x_node_type)[0].squeeze(0)  # Remove sequence dimension
            if self.bidirectional:
                h = h_n[-2] + h_n[-1]
            else:
                h = h_n[-1]
            embeddings[idx] = h

        return embeddings.masked_fill(empty.unsqueeze(-1), 0.0)  # Fill embeddings for empty sequences with zeros
            

class MarketHGTModel(nn.Module):
    def __init__(
            self, in_hid:int, out_hid:int, num_head:int, dropout:float, node_type_cfg: Dict[str, int], bidirectional: bool = False):
        super().__init__()
        self.gru = myGRU(out_hid, node_type_cfg, bidirectional)
        self.hgt_conv = conv.MarketHGTConv(in_hid, out_hid, num_head, dropout)
        self.classifier = Classifier(out_hid)

    def forward(self, x, edge_index, node_type_i, node_type_j, edge_type_array, target):
        # Pass through GRU
        x = self.gru(x, node_type_i)  # Assuming node_type_i represents the node types for GRU
        # Pass through HGTConv
        x = self.hgt_conv(x, edge_index, node_type_i, node_type_j, edge_type_array)
        
        # Pass through classifier
        return self.classifier(x, target)  # Assuming classifier takes x and target for loss computation