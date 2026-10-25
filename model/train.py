import argparse
import torch
from torch.nn import CrossEntropyLoss
from torch.optim import Adam
from typing import Dict, List, Tuple

from model.model import MarketHGTModel
# import scripts.datap.graph.loader as loader
import scripts.datap.graph.const as c
from scripts.datap.graph.dataset import MarketDataset

LOSS_FN = CrossEntropyLoss()  # Using CrossEntropyLoss for multi-class classification # Using Adam optimizer for training
NODENAME2NODEID = {'stock':0, 'statement':1, 'mktIdx':2, 'future':3}

def train(model:MarketHGTModel, dataset: MarketDataset, optimizer:Adam, epoch:int):

    train_losses = []
    valid_losses = []

    for e in range(epoch):

        epock_train_losses = []
        epock_valid_losses = []

        for idx in range(c.TRAIN_RANGE_BY_TFID[0], c.TRAIN_RANGE_BY_TFID[1] + 1):

            data = dataset.get(idx)
            
            optimizer.zero_grad()

            # check order of lnIDs
            lnIDs        = torch.cat([data[nt].lnIDs for nt in c.HETERO_NODE_TYPES], dim=0).to(c.DEVICE)
            assert sum(lnIDs[t] - (lnIDs[t-1] + 1) for t in range(1, len(lnIDs))) == 0, "lnIDs should be consecutive integers"

            x       = [data[nt].x for nt in c.HETERO_NODE_TYPES] # becuase of different input dimension for each node type
            ntIDs   = torch.cat([data[nt].ntID    for nt in c.HETERO_NODE_TYPES], dim=0).to(c.DEVICE)
            target  = torch.cat([data[nt].target  for nt in c.HETERO_NODE_TYPES], dim=0).to(c.DEVICE)
            seq_len = torch.cat([data[nt].seq_len for nt in c.HETERO_NODE_TYPES], dim=0).to(c.DEVICE)
            
            edge_index = torch.cat([data[edge_type].edge_index for edge_type in c.HETERO_EDGE_UNIT.keys()], dim=1).to(c.DEVICE)
            etIDs  = torch.cat([data[edge_type].etIDs      for edge_type in c.HETERO_EDGE_UNIT.keys()], dim=0).to(c.DEVICE)
            
            labels = data["stock"].labels

            output = model(x, seq_len, edge_index, ntIDs, etIDs, target)

            loss = LOSS_FN(output, labels)
            epock_train_losses.append(loss.item())
            loss.backward()
            optimizer.step()
    
        train_losses.append(sum(epock_train_losses))

        for idx in range(c.VALID_RANGE_BY_TFID[0], c.VALID_RANGE_BY_TFID[1] + 1):

            data = dataset.get(idx)
            
            optimizer.zero_grad()

            # check order of lnIDs
            lnIDs        = torch.cat([data[nt].lnIDs for nt in c.HETERO_NODE_TYPES], dim=0).to(c.DEVICE)
            assert sum(lnIDs[t] - (lnIDs[t-1] + 1) for t in range(1, len(lnIDs))) == 0, "lnIDs should be consecutive integers"

            x       = [data[nt].x for nt in c.HETERO_NODE_TYPES] # becuase of different input dimension for each node type
            ntIDs   = torch.cat([data[nt].ntID    for nt in c.HETERO_NODE_TYPES], dim=0).to(c.DEVICE)
            target  = torch.cat([data[nt].target  for nt in c.HETERO_NODE_TYPES], dim=0).to(c.DEVICE)
            seq_len = torch.cat([data[nt].seq_len for nt in c.HETERO_NODE_TYPES], dim=0).to(c.DEVICE)
            
            edge_index = torch.cat([data[edge_type].edge_index for edge_type in c.HETERO_EDGE_UNIT.keys()], dim=1).to(c.DEVICE)
            etIDs  = torch.cat([data[edge_type].etIDs      for edge_type in c.HETERO_EDGE_UNIT.keys()], dim=0).to(c.DEVICE)
            
            labels = data["stock"].labels

            output = model(x, seq_len, edge_index, ntIDs, etIDs, target)

            loss = LOSS_FN(output, labels)
            epock_train_losses.append(loss.item())

        valid_losses.append(sum(epock_valid_losses)/c.VALID_LENGTH)

        print(
            f'Epoch {e+1}/{epoch}\n\
              Train Loss: {sum(epock_train_losses)/c.TRAIN_LENGTH:.4f}\n\
              Valid Loss: {sum(epock_valid_losses)/c.VALID_LENGTH:.4f}'
            )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train the MarketHGTModel.")
    parser.add_argument("--in-hid"    , type=int  , default=128, help="Input hidden dimension.")
    parser.add_argument("--out-hid"   , type=int  , default=128, help="Output hidden dimension.")
    parser.add_argument("--num-head"  , type=int  , default=4  , help="Number of attention heads.")
    parser.add_argument("--dropout"   , type=float, default=0.1, help="Dropout rate.")
    parser.add_argument("--epochs"    , type=int  , default=32 , help="Number of epochs to train.")
    parser.add_argument("--num-layer" , type=int  , default=2  , help="Number of GNN layers.")
    parser.add_argument("--lr"        , type=float, default=0.001, help="Learning rate.")
    parser.add_argument('--bidirectional', action='store_true', help="Use bidirectional GRU.")
    args = parser.parse_args()

    model = MarketHGTModel(
        in_hid        = args.in_hid, 
        out_hid       = args.out_hid, 
        num_head      = args.num_head, 
        num_layers    = args.num_layer,
        dropout       = args.dropout,
        bidirectional  = False
    ).to(c.DEVICE)

    # Load the dataset by get-method with tfID
    dataset = MarketDataset(root="pt")

    optimizer = Adam(model.parameters(), lr=0.001)

    model.train()
    train(model, dataset, optimizer=optimizer, epoch=args.epochs)