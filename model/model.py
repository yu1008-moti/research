import model.conv as conv
import scripts.datap.graph.const as c
from itertools import compress
from torch_geometric.data import HeteroData
from torch.nn.functional import softmax

from torch import nn
import torch
from typing import Dict, List, Tuple
from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence

NUM_LABELS = c.NUM_LABELS  # Assuming 3 classes for classification
DEVICE = c.DEVICE

def get_data_attr(data:HeteroData):
    # check order of lnIDs
    lnIDs      = torch.cat([data[nt].lnID for nt in c.HETERO_NODE_TYPES], dim=0).to(c.DEVICE)
    assert sum(lnIDs[1:] - lnIDs[:-1] != 1) == 0, "lnIDs should be consecutive integers"
    x          = [data[nt].x for nt in c.HETERO_NODE_TYPES] # becuase of different input dimension for each node type
    lnIDs      = [data[nt].lnID for nt in c.HETERO_NODE_TYPES] # it use for check order of lnIDs and index
    ntIDs      = torch.cat([data[nt].ntID    for nt in c.HETERO_NODE_TYPES], dim=0).to(c.DEVICE)
    target     = data['stock'].target.to(c.DEVICE)
    seq_len    = torch.cat([data[nt].seq_len for nt in c.HETERO_NODE_TYPES], dim=0).to(c.DEVICE)
    edge_index = torch.cat([data[edge_type].edge_index for edge_type in c.HETERO_EDGE_UNIT.keys()], dim=1).to(c.DEVICE)
    etIDs      = torch.cat([data[edge_type].etID         for edge_type in c.HETERO_EDGE_UNIT.keys()], dim=0).to(c.DEVICE)

    return x, lnIDs, seq_len, edge_index, ntIDs, etIDs, target


class Classifier(nn.Module):
    def __init__(self, in_hid:int):
        super().__init__()
        self.classifier = nn.Linear(in_hid, NUM_LABELS)  # Assuming 3 classes for classification
        self.softmax = nn.Softmax(dim=1)  # Softmax for multi-class classification

    def forward(self, h):
        return self.softmax(self.classifier(h))

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

    def forward(self, x:List[torch.Tensor], lnIDs:List[torch.Tensor], seq_len:List[torch.Tensor], ntIDs: torch.Tensor) -> torch.Tensor:

        emb = torch.zeros(len(x[0])+len(x[1])+len(x[2])+len(x[3]), self.hidden_size, device=DEVICE)

        for ntID in c.HETERO_NODE_ID.values():
            # empty = seq_len[node_type] == 0
            idx = ntIDs == ntID
            lens = seq_len[idx].clamp(min=1, max=25).to('cpu')  # Ensure lengths are at least 1 and at most 25
            x_nt = x[ntID].to(DEVICE)
            packed = pack_padded_sequence(x_nt, lens, batch_first=True, enforce_sorted=False)
            assert packed.sorted_indices is not None, "Packed sequence does not have sorted indices"
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

    def forward(self, data:HeteroData):
        # Get the data attributes
        x, lnIDs, seq_len, edge_index, ntIDs, etIDs, target = get_data_attr(data)

        # Pass through GRU
        h = self.gru(x, lnIDs, seq_len, ntIDs)  # Assuming node_type_i represents the node types for GRU
        # Pass through HGTConv
        h = self.hgt_conv(h, edge_index, ntIDs, etIDs)

        h = h[ntIDs==0][target==1]  # Select only the nodes that are targets for classification
        
        # Pass through classifier
        return self.classifier(h)  # Assuming classifier takes x and target for loss computation