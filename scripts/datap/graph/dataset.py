import torch
from torch import nn
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
        print(f'db_ver: {c.DB_VERSION}')
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
            tIDs, attr, etID = corr_info['tIDs'], corr_info['attr'], corr_info['etID']
            del corr_info  # Free memory
        assert edge_index.shape[1] == len(tIDs) == len(attr) == len(etID) > 0, "The loaded edge data from 'corr_edge_info.npz' is inconsistent or empty."
        return {'edge_index': edge_index, 'tID': tIDs, 'attr': attr, 'etID': etID}

    def process(self):
        if self.undo: return

        # These tools are used to thier relevant job
        tIDs = h.get_tIDs(self.conn)

        # Load all node data for all node types into memory to avoid repeated database queries
        node_data_master = h.get_node_data_master(self.conn)

        # pre-process the correlation edge data and save it to a file for later use
        pre_process_results = self.pre_process()

        # Set up labels for eval nodes
        h.set_labels(self.conn)

        # Create HeteroData objects for each dateID
        print(f"Creating HeteroData objects for tIDs in range [{c.USE_MIN_TFID}, {c.USE_MAX_TFID}]...")
        for i, tID in enumerate(tIDs, 1):
            if not (tID < c.USE_MIN_TFID or tID > c.USE_MAX_TFID): 
                data = HeteroData()
                h.set_edges(self.conn, tID, data, pre_process_results)
                h.set_nodes(self.conn, tID, data, node_data_master)
                torch.save(data, os.path.join(self.processed_dir, f'data_{tID}.pt'))
            print(f'\r[{i:4d}/{len(tIDs)}] Processed tID: {tID}', end='')
        print("\ncreated Graph Objects over all tIDs.")

    def len(self):
        return len(self.processed_file_names)

    def get(self, tID:int) -> HeteroData:
        if tID < c.USE_MIN_TFID or tID > c.USE_MAX_TFID:
            raise IndexError("Index out of range")
        data_path = os.path.join(self.processed_dir, f'data_{tID}.pt')
        data = torch.load(data_path, weights_only=False)
        return data