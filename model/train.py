import argparse
import torch
from torch.nn import CrossEntropyLoss
from torch.optim import Adam
from typing import Dict, List, Tuple

from model.model import MarketHGTModel
import scripts.datap.graph.loader as loader


HETERO_EDGE_DICT: Dict[str, List[str]] = {
    "corr"          : ['stock' , 'stock'],
    "made_up_Mkt"   : ['stock' , 'mktIdx'],
    "made_up_topix" : ['stock' , 'mktIdx'],
    "made_up_s33"   : ['stock' , 'mktIdx'],
    "made_up_s17"   : ['stock' , 'mktIdx'],
    "recent_report" : ['stock' , 'statement'],
    "index_future"  : ['mktIdx', 'future']
}

HETERO_NODE_TYPES: List[str] = [
    'stock',
    'statement',
    'mktIdx',
    'future'
]

HETERO_EDGE_ID: Dict[str, int] = {
    "corr"          : 0,
    "made_up_Mkt"   : 1,
    "made_up_topix" : 2,
    "made_up_s33"   : 3,
    "made_up_s17"   : 4,
    "recent_report" : 5,
    "index_future"  : 6
}

HETERO_NODE_ID: Dict[str, int] = {
    "stock"        : 0,
    "statement"    : 1,
    "mktIdx"       : 2,
    "future"       : 3 
}

# select count(*)-4 as num_cols from (describe '.\*\*.parquet');
# "4" means "tfID", "codeID", "dateID", "nodeID" columns
NODE_TYPE_CFG: Dict[str, int] = {
    "stock"        : 16,
    "statement"    : 60,
    "mktIdx"       : 4,
    "future"       : 16
}

LOSS_FN = CrossEntropyLoss()  # Using CrossEntropyLoss for multi-class classification # Using Adam optimizer for training

def train(model:MarketHGTModel, optimizer:Adam, epoch:int):

    train_loader, valid_loader, eval_loader = loader.get_dataloaders()

    train_losses = []
    valid_losses = []

    for e in range(epoch):

        epock_train_losses = []
        epock_valid_losses = []

        for data in train_loader:
            
            optimizer.zero_grad()

            x            = torch.cat([data[node_type].x for node_type in HETERO_NODE_TYPES], dim=0)
            target       = torch.cat([data[node_type].target for node_type in HETERO_NODE_TYPES], dim=0)
            labels       = data["stock"].labels
            
            edge_index   = torch.cat([data[edge_type].edge_index  for edge_type in HETERO_EDGE_DICT.keys()], dim=1)
            node_type_i  = torch.cat([data[edge_type].node_type_i for edge_type in HETERO_EDGE_DICT.keys()], dim=0)
            node_type_j  = torch.cat([data[edge_type].node_type_j for edge_type in HETERO_EDGE_DICT.keys()], dim=0)
            edge_type_ij = torch.cat([data[edge_type].edge_type   for edge_type in HETERO_EDGE_DICT.keys()], dim=0)

            output = model(x, edge_index, node_type_i, node_type_j, edge_type_ij, labels, target)

            loss = LOSS_FN(output, labels)
            epock_train_losses.append(loss.item())
            loss.backward()
            optimizer.step()
    
        train_losses.append(sum(epock_train_losses))

        for data in valid_loader:
            x            = torch.cat([data[node_type].x for node_type in HETERO_NODE_TYPES], dim=0)
            target       = torch.cat([data[node_type].target for node_type in HETERO_NODE_TYPES], dim=0)
            labels       = data["stock"].labels
            
            edge_index   = torch.cat([data[edge_type].edge_index  for edge_type in HETERO_EDGE_DICT.keys()], dim=1)
            node_type_i  = torch.cat([data[edge_type].node_type_i for edge_type in HETERO_EDGE_DICT.keys()], dim=0)
            node_type_j  = torch.cat([data[edge_type].node_type_j for edge_type in HETERO_EDGE_DICT.keys()], dim=0)
            edge_type_ij = torch.cat([data[edge_type].edge_type   for edge_type in HETERO_EDGE_DICT.keys()], dim=0)

            output = model(x, edge_index, node_type_i, node_type_j, edge_type_ij, labels, target)

            loss = LOSS_FN(output, labels)
            epock_valid_losses.append(loss.item())

        valid_losses.append(sum(epock_valid_losses)/len(valid_loader))

        print(
            f'Epoch {e+1}/{epoch}\n\
              Train Loss: {sum(epock_train_losses)/len(train_loader):.4f}\n\
              Valid Loss: {sum(epock_valid_losses)/len(valid_loader):.4f}'
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
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"

    model = MarketHGTModel(
        in_hid        = args.in_hid, 
        out_hid       = args.out_hid, 
        num_head      = args.num_head, 
        dropout       = args.dropout,
        node_type_cfg = NODE_TYPE_CFG
    ).to(device)

    optimizer = Adam(model.parameters(), lr=0.001)

    model.train()
    train(model, optimizer=optimizer, epoch=args.epochs)