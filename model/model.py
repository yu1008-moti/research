import model.conv as conv
import scripts.datap.graph.const as c
from itertools import compress

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
    def __init__(self, hidden_size: int, bidirectional: bool = False):
        super().__init__()
        self.node_type_input_num = c.NODE_TYPE_INPUT_NUM
        self.hidden_size = hidden_size
        self.bidirectional = bidirectional
        
        self.linear_layers = nn.ModuleList([
            nn.Linear(hidden_size*2, hidden_size)
        ])

        self.GRUs = nn.ModuleList([
            nn.GRU(
                in_dim,
                self.hidden_size,
                batch_first=True,
                bidirectional=bidirectional
            ) 
            for in_dim in self.node_type_input_num.values()
        ])

    def forward(self, x:List[torch.Tensor], seq_len, ntIDs) -> torch.Tensor:

        emb = torch.zeros(len(x), self.hidden_size, device=DEVICE)

        for ntID in c.HETERO_NODE_ID.values():
            # empty = seq_len[node_type] == 0
            lens = seq_len[ntID].clamp(min=1)
            idx = ntIDs == ntID
            x_nt = torch.cat(list(compress(x, idx.tolist())), dim=0).to(DEVICE)
            packed = pack_padded_sequence(x_nt, lens, batch_first=True, enforce_sorted=False)
            assert packed.sorted_indices is not None, "Packed sequence does not have sorted indices"
            idx_end += len(packed.sorted_indices)
            _, h_n = self.GRUs[ntID](packed) # return is (output, hidden-state), we only need the hidden state
            if self.bidirectional:
                h = torch.cat([h_n[-2], h_n[-1]], dim=-1)
                h = self.linear_layers[ntID](h)  # Apply linear layer to reduce dimension
            else:
                h = h_n[-1]
            emb[idx] = h

        return emb
            

class MarketHGTModel(nn.Module):
    def __init__(
            self, in_hid:int, out_hid:int, num_head:int, num_layers:int, dropout:float, bidirectional: bool = False):
        super().__init__()
        
        self.gru = myGRU(out_hid, bidirectional)
        self.hgt_conv = conv.GNNModel(in_hid, out_hid, num_head, num_layers, dropout)
        self.classifier = Classifier(out_hid)

    def forward(self, x:List[torch.Tensor], seq_len, edge_index, ntIDs: torch.Tensor, etIDs: torch.Tensor, target):
        # Pass through GRU
        # forward(self, x, seq_len, x_node_types):
        h = self.gru(x, seq_len, ntIDs)  # Assuming node_type_i represents the node types for GRU
        # Pass through HGTConv
        x = self.hgt_conv(h, edge_index, ntIDs, etIDs)
        
        # Pass through classifier
        return self.classifier(x, target)  # Assuming classifier takes x and target for loss computation