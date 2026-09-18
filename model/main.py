import torch
from torch import nn
from torch.utils.data import Dataset, DataLoader
from torch_geometric.loader import NeighborLoader
import numpy as np
import duckdb as db
import pandas as pd


class GraphDataSet(Dataset):
    def __init__(self, graph_list):
        self.data = graph_list

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        return self.data[idx]