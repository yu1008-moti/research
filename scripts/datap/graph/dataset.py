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


__all__ = ['MarketDataset']


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
        try:
            self.conn = sql.connect(":memory:")
            self.conn.execute(f"attach '{c.ACT_DB_PATH}' as act;")
            self.conn.execute(f"attach '{c.DEV_DB_PATH}' as dev;")
            self.conn.execute(f"use act;")
            super().__init__(root)
        except Exception as e:
            print(f"Error connecting to the database: {e}")
            raise
        finally:
            if hasattr(self, 'conn'):
                self.conn.close()

    @property
    def processed_file_names(self):
        return [f'data_{dateID}.pt' for dateID in range(c.USE_MIN_TFID, c.USE_MAX_TFID + 1)] # default range : 1 to 6448

    def pre_process(self) -> Dict[str, np.ndarray]:
        # set "corr" edge
        print("Pre-processing the 'corr' edge type...")
        if not os.path.exists(c.CORR_EDGE_INFO_PATH):
            capm_data = self.conn.execute("SELECT * from tools.capm_tool;").df()
            edge_index, tIDs, attr = stock_corr_stock.get_corr_edge(capm_data)
            etID = np.full_like(tIDs, c.HETERO_EDGE_ID["corr"], dtype=c.NP_INT32)
            np.savez(c.CORR_EDGE_INFO_PATH, edge_index=edge_index, tIDs=tIDs, attr=attr, etID=etID)
            del capm_data  # Free memory
        else:
            corr_info = np.load(c.CORR_EDGE_INFO_PATH)
            edge_index = corr_info['edge_index']
            tIDs = corr_info['tIDs'] # later, we use "tID" for dict key.
            attr = corr_info['attr']
            etID = corr_info['etID']
            del corr_info  # Free memory
        assert edge_index.shape[1] == len(tIDs) == len(attr) == len(etID) > 0, "The loaded edge data from 'corr_edge_info.npz' is inconsistent or empty."
        return {'edge_index': edge_index, 'tID': tIDs, 'attr': attr, 'etID': etID}

    def process(self):
        
        if self.undo: return

        # Read data into huge `Data` list.
        # data_list = []
        global_edges: Dict[int, Any] = {}
        global_nodes: Dict[int, Any] = {}

        # These tools are used to thier relevant job
        print("Loading tools from the database...")
        date_tools = self.conn.execute(f"SELECT * from tools.date_tool where tID < {c.MAX_TID};").df()
        node_tools = self.conn.execute(f"SELECT * from tools.node_tool where tID < {c.MAX_TID};").df()
        assert not date_tools.empty, "Date tools is empty. Please check the database."
        assert not node_tools.empty, "Node tools is empty. Please check the database."
        print("Tools loaded successfully.\n")

        # Set up the entire_data dictionary
        global_edges = h.get_global_edges(self.conn, self.pre_process())
        global_nodes = h.get_global_nodes(self.conn)

        # Set up labels for eval nodes
        returns = self.conn.execute("SELECT * from labels.mv3;").df()
        h.set_labels(returns)  # Set labels for the returns DataFrame

        num_tIDs = len(date_tools.loc[:, 'tID'])

        # Create HeteroData objects for each dateID
        print(f"Creating HeteroData objects for tIDs in range [{c.USE_MIN_TFID}, {c.USE_MAX_TFID}]...")
        for i, tID in enumerate(date_tools.loc[:, 'tID'], 1):
            if not (tID < c.USE_MIN_TFID or tID > c.USE_MAX_TFID): 
                # Initialize a new HeteroData.
                data = HeteroData()

                # Set edges for the current tID
                h.set_edge_HeteroData(data, tID, global_edges)

                # Pick up nodes by HGTsampling
                # Also, HGTsampling filter edges corresponding to the sampled nodes
                # init_OS = returns.loc[returns['tID'] == tID, 'cID'].to_list()
                # HGTsampling(data, init_OS, L=2, n=20, display=False)

                # Set sampled nodes for the current tID
                h.set_node_HeteroData(data, tID, global_nodes, node_tools)
                    
                torch.save(data, os.path.join(self.processed_dir, f'data_{tID}.pt'))
            print(f'\r[{i:4d}/{num_tIDs}] Processed tID: {tID}', end='')
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

