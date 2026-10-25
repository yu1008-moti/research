import torch
from torch_geometric.data import HeteroData
from torch_geometric.data import InMemoryDataset, Dataset
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Any, Tuple
import duckdb as sql

import scripts.datap.graph.stock_corr_stock  as stock_corr_stock
import scripts.datap.graph.const as c
from scripts.datap.graph.sampling import HGTsampling
import scripts.datap.graph.dataset_helper as h
import os


__all__ = ['MarketDataset', 'train_valid_eval_split']


def get_parquet_path(name: str) -> Path:
    return c.PARQUET_DISR / f"{name}.parquet"
    
def set_labels(return_df: pd.DataFrame) -> None:

    train_mask = return_df['dateID'].between(c.TRAIN_RANGE_BY_DATEID[0], c.TRAIN_RANGE_BY_DATEID[1])
    define_labels_samples = return_df[train_mask]
    num_define_labels_samples = len(define_labels_samples)

    q1 = int(num_define_labels_samples*1/3)
    q2 = int(num_define_labels_samples*2/3)

    sorted_returns = define_labels_samples.sort_values(by='return')
    low_threshold = sorted_returns.iloc[q1]['return']
    high_threshold = sorted_returns.iloc[q2]['return']

    return_df['neg'] = (return_df['return'] < low_threshold).astype(int)
    return_df['pos'] = (return_df['return'] > high_threshold).astype(int)
    return_df['neu'] = ((return_df['return'] >= low_threshold) & (return_df['return'] <= high_threshold)).astype(int)

    print("\nREPORT: Labeling of returns based on thresholds")
    print(f"Number of samples used to define thresholds: {num_define_labels_samples}")
    print(f"Label thresholds   : low={low_threshold}, high={high_threshold}")
    print(f"Label distribution : neg={return_df['neg'].sum()}, pos={return_df['pos'].sum()}, neu={return_df['neu'].sum()}")
    print(f'(%) neg : neu : pos = {return_df["neg"].sum()/len(return_df):.5%} : {return_df["neu"].sum()/len(return_df):.5%} : {return_df["pos"].sum()/len(return_df):.5%}\n')

def train_valid_eval_split(data_list:List) -> Tuple[List[HeteroData], List[HeteroData], List[HeteroData]]:

    dateID = pd.read_parquet(get_parquet_path(c.DATE_ID_FILE_ALIAS))

    assert all(isinstance(data, HeteroData) for data in data_list), "All elements in data_list must be instances of HeteroData"

    train_mask = dateID['dateID'].between(c.TRAIN_RANGE_BY_DATEID[0], c.TRAIN_RANGE_BY_DATEID[1])
    valid_mask = dateID['dateID'].between(c.VALID_RANGE_BY_DATEID[0], c.VALID_RANGE_BY_DATEID[1])
    eval_mask  = dateID['dateID'].between(c.EVAL_RANGE_BY_DATEID[0] , c.EVAL_RANGE_BY_DATEID[1])

    del dateID  # Free memory

    train_data = [data for i, data in enumerate(data_list) if train_mask.iloc[i]]
    valid_data = [data for i, data in enumerate(data_list) if valid_mask.iloc[i]]
    eval_data  = [data for i, data in enumerate(data_list) if eval_mask.iloc[i]]

    return train_data, valid_data, eval_data


class MarketDataset(Dataset):
    def __init__(
            self, 
            root,
        ):
        self.undo = False
        
        print(f'device: {c.DEVICE}')
        if os.path.exists(os.path.join(root, "processed")):
            print(f"Processed data found in {os.path.join(root, 'processed')}. Skipping processing.")
            self.undo = True
        self.conn = sql.connect(database=c.DB_PATH, read_only=True)
        super().__init__(root)

    @property
    def raw_dir(self):
        return Path(__file__).parent / "pt/raw"

    @property
    def raw_file_names(self):
        pass

    @property
    def processed_file_names(self):
        return [f'data_{dateID}.pt' for dateID in range(c.USE_MIN_TFID, c.USE_MAX_TFID + 1)] # default range : 1 to 6448

    def pre_process(self) -> Dict[str, np.ndarray]:
        # set "corr" edge
        if not os.path.exists(c.CORR_EDGE_INFO_PATH):
            capm_data = self.conn.execute("SELECT * from tools.capm_data").fetchdf()
            edge_index, tIDs, attr = stock_corr_stock.get_corr_edge(capm_data)
            etID = np.full_like(tIDs, c.HETERO_EDGE_ID["corr"], dtype=c.NP_INT32)
            np.savez(c.CORR_EDGE_INFO_PATH, edge_index=edge_index, tIDs=tIDs, attr=attr, etID=etID)
            del capm_data  # Free memory
        else:
            edge_index, tIDs, attr, etID = np.load(c.CORR_EDGE_INFO_PATH)
        assert len(edge_index) == len(tIDs) == len(attr) == len(etID) == 0, "Expected empty arrays for corr_edge_info"
        return {'edge_index': edge_index, 'tIDs': tIDs, 'attr': attr, 'etIDs': etID}

    def process(self):
        
        if self.undo: return

        # Read data into huge `Data` list.
        # data_list = []
        global_edges: Dict[int, Any] = {}
        global_nodes: Dict[int, Any] = {}

        # These tools are used to thier relevant job
        date_tools = self.conn.execute("SELECT * from tools.date_tool").fetchdf()
        node_tools = self.conn.execute("SELECT * from tools.node_tool").fetchdf()

        # Set up the entire_data dictionary
        global_edges = h.get_global_edges(self.conn, self.pre_process())
        global_nodes = h.get_global_nodes(self.conn)

        # Set up labels for eval nodes
        returns = self.conn.execute("select * from labels.mv3").fetchdf()
        set_labels(returns)  # Set labels for the returns DataFrame

        # Create HeteroData objects for each dateID
        for i, tID in enumerate(date_tools.loc[:, 'tID'], 1):
            if tID < c.USE_MIN_TFID or tID > c.USE_MAX_TFID: continue

            # Initialize a new HeteroData.
            data = HeteroData()

            # Set edges for the current tID
            h.set_edge_HeteroData(data, tID, global_edges)

            # Pick up nodes by HGTsampling
            # Also, HGTsampling filter edges corresponding to the sampled nodes
            init_OS = returns.loc[returns['tIDs'] == tID, 'cID'].to_list()
            HGTsampling(data, init_OS, L=2, n=20, display=False)

            # Set sampled nodes for the current tID
            h.set_node_HeteroData(data, tID, global_nodes, node_tools)
                
            torch.save(data, os.path.join(self.processed_dir, f'data_{tID}.pt'))
            print(f'\rtID: {tID},  {i}/{c.USE_MAX_TFID}', end='')
        print("\ncreated Graph Objects over all tIDs.")

    def len(self):
        return len(self.processed_file_names)

    def get(self, tID:int) -> HeteroData:
        """
        Get a HeteroData object by its tID.
        """
        # print(f"Fetching data for tID: {tID}")
        if tID < c.USE_MIN_TFID or tID > c.USE_MAX_TFID:
            raise IndexError("Index out of range")
    
        data_path = os.path.join(self.processed_dir, f'data_{tID}.pt')
        data = torch.load(data_path, weights_only=False)
        return data