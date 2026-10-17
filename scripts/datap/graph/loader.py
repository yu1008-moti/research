from pathlib import Path
import pandas as pd
from typing import List, Tuple
from torch_geometric.data import HeteroData
from torch_geometric.loader import DataLoader

from scripts.datap.graph.dataset import MarketDataset, train_valid_eval_split

__all__ = ['get_dataloaders']


def get_dataloaders() -> Tuple[DataLoader, DataLoader, DataLoader]:
    ds = MarketDataset(root='./pt')
    data_list = list(ds)

    train_data, valid_data, eval_data = train_valid_eval_split(data_list)

    train_loader = DataLoader(train_data, shuffle=False)
    valid_loader = DataLoader(valid_data, shuffle=False)
    eval_loader  = DataLoader(eval_data,  shuffle=False)

    return train_loader, valid_loader, eval_loader