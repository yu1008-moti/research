import torch
from torch_geometric.data import HeteroData
from torch_geometric.data import InMemoryDataset
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Set

import stock_corr_stock

##################################################################
MAX_DATEID = 6554 # include this dateID
PARQUET_DISR = Path("db/parquet")
# REMOVE_CODE_ID = [3622] # because of the length, shape is (1,)
##################################################################

def get_parquet_path(name: str) -> Path:
    return PARQUET_DISR / f"{name}.parquet"

HETERO_EDGE_DICT: Dict[str, Set[str]] = {
    "corr"          : {'stock' , 'stock'},
    "made_up_Mkt"   : {'stock' , 'mktIdx'},
    "made_up_topix" : {'stock' , 'topix'},
    "made_up_s33"   : {'stock' , 's33'},
    "made_up_s17"   : {'stock' , 's17'},
    "recent_report" : {'stock' , 'statement'},
    "index_future"  : {'mktIdx', 'future'}
}

# <duckdb side processing>
# dateID is limited to 6554 (SQL: ... where dateID < 6555)
# if "ri" is nan or inf, replace it with 0.0 (SQL ... set ri=if(isnan(ri) or isinf(ri) or ri is NULL, 0, ri))
CAPM_DATA_FILE_ALIAS = "capm_data"

DATE_ID_FILE_ALIAS = "dateID"

class MarketDataset(InMemoryDataset):
    def __init__(
            self, 
            root='./pt', 
            transform=None, 
            pre_transform=None, 
        ):

        print(f'device: {torch.device("cuda" if torch.cuda.is_available() else "cpu")}')
        super().__init__(root, transform, pre_transform)
        self.data_list = torch.load(self.processed_paths[0])

    @property
    def raw_dir(self):
        return Path(self.root) / 'parquet'

    @property
    def raw_file_names(self):
        return [
            "raw_stocks.pt",
            "raw_statements.pt",
            "raw_futures.pt",
            "raw_mkt_index.pt",
        ]

    @property
    def processed_file_names(self):
        return ['processed_market_data.pt']

    def pre_process(self):
        # set "corr" edge
        capm_data = pd.read_parquet(get_parquet_path(CAPM_DATA_FILE_ALIAS))
        return stock_corr_stock.get_corr_edge(capm_data)

    def process(self):
        # Read data into huge `Data` list.
        data_list = []
        entire_data = {}

        # dateIDs for the entire dataset
        dateIDs = pd.read_parquet(get_parquet_path(DATE_ID_FILE_ALIAS))["dateID"].values
        assert isinstance(dateIDs, np.ndarray), f"dateIDs should be a numpy array, got {type(dateIDs)}"
        dateIDs = np.sort(dateIDs)

        # corr edge
        corr_edge_info = self.pre_process()

        # Set up the entire_data dictionary
        for key in HETERO_EDGE_DICT.keys():
            if key == "corr":
                edge_index, dateIDs, edge_attr = corr_edge_info
            else:
                edge_df = pd.read_parquet(get_parquet_path(key))

                ### FILTERING
                edge_df = edge_df[edge_df["dateID"] <= MAX_DATEID]  # Filter by MAX_DATEID
                ###

                node1_type, node2_type = HETERO_EDGE_DICT[key]
                edge_index = edge_df[[f"{node1_type}_nodeID", f"{node2_type}_nodeID"]].values.T
                observable = edge_df["dateID"].values
                edge_attr  = np.ones(edge_index.shape[1], dtype=np.float32)  # Placeholder for edge attributes
            entire_data[key] = {
                'edge_index': edge_index,
                'observable': observable,
                'edge_attr': edge_attr
            }

        # Create HeteroData objects for each dateID
        for dateID in dateIDs:
            self.data = HeteroData()

            for edge_type, edge_info in entire_data.items():
                edge_index = edge_info['edge_index']
                observable = edge_info['observable']
                edge_attr  = edge_info['edge_attr']

                node1_type, node2_type = HETERO_EDGE_DICT[edge_type]

                idx = np.where(observable == dateID)[0]
                self.data[node1_type, edge_type, node2_type].edge_index = torch.tensor(edge_index[:, idx], dtype=torch.long)
                self.data[node1_type, edge_type, node2_type].edge_attr = torch.tensor(edge_attr[idx], dtype=torch.float32)

            data_list.append(self.data)
        
        torch.save(data_list, self.processed_paths[0])