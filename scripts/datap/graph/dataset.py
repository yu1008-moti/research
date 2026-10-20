import torch
from torch_geometric.data import HeteroData
from torch_geometric.data import InMemoryDataset, Dataset
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Any, Tuple
from torch.nn.utils.rnn import pad_sequence

import scripts.datap.graph.stock_corr_stock  as stock_corr_stock
import scripts.datap.graph.const as c
from scripts.datap.graph.sampling import HGTsampling
import os


__all__ = ['MarketDataset', 'train_valid_eval_split']


def get_parquet_path(name: str) -> Path:
    return c.PARQUET_DISR / f"{name}.parquet"

def get_occurence_mask(df: pd.DataFrame, col: str, dateID: int, num_iccur_window_size: int) -> pd.Series:
    df_o = df[df['nodeType']==col].sort_values(by=['dateID', 'codeID']).copy()
    df_o['current_num_occur'] = df_o['codeID'].map((
        df[(df['nodeType']==col) & (df['dateID'] <= dateID)].sort_values(by=['dateID', 'codeID'])
    ).groupby('codeID')['num_occur'].max())
    mask = df_o['current_num_occur'] < num_iccur_window_size
    assert isinstance(mask, pd.Series), f"Expected mask to be a pandas Series, got {type(mask)}"
    del df_o  # Free memory
    return mask
    
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

    print("\n====================== REPORT: Labeling of returns based on thresholds ======================")
    print(f"Number of samples used to define thresholds: {num_define_labels_samples}")
    print(f"Label thresholds   : low={low_threshold}, high={high_threshold}")
    print(f"Label distribution : neg={return_df['neg'].sum()}, pos={return_df['pos'].sum()}, neu={return_df['neu'].sum()}")
    print(f'(%) neg : neu : pos = {return_df["neg"].sum()/len(return_df):.5%} : {return_df["neu"].sum()/len(return_df):.5%} : {return_df["pos"].sum()/len(return_df):.5%}')
    print("=============================================================================================")

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
        
        print(f'device: {torch.device("cuda" if torch.cuda.is_available() else "cpu")}')
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

    def pre_process(self):
        # set "corr" edge
        capm_data = pd.read_parquet(get_parquet_path(c.CAPM_DATA_FILE_ALIAS))
        return stock_corr_stock.get_corr_edge(capm_data)

    def process(self):

        # Read data into huge `Data` list.
        data_list = []
        entire_edges = {}
        entire_nodes = {}

        # dateIDs for the entire dataset
        dateIDs = pd.read_parquet(get_parquet_path(c.DATE_ID_FILE_ALIAS), columns=["dateID"])
        assert isinstance(dateIDs, pd.DataFrame), f"dateIDs should be a pandas DataFrame, got {type(dateIDs)}"
        dateIDs = np.sort(dateIDs).T[0]

        # tfIDs for the entire dataset
        tfIDs = pd.read_parquet(get_parquet_path(c.DATE_ID_FILE_ALIAS), columns=["tfID"])
        assert isinstance(tfIDs, pd.DataFrame), f"tfIDs should be a numpy array, got {type(tfIDs)}"
        tfIDs = np.sort(tfIDs).T[0]

        dateID_to_tfid = dict(zip(dateIDs, tfIDs))

        # nodeID_table for the entire dataset
        nodeID_table = pd.read_parquet(get_parquet_path(c.NODE_ID_FILE_ALIAS))
        assert isinstance(nodeID_table, pd.DataFrame), f"nodeID_table should be a pandas DataFrame, got {type(nodeID_table)}"

        # corr edge
        if not os.path.exists(c.CORR_EDGE_INFO_PATH):
            corr_edge_info = self.pre_process()
            torch.save(corr_edge_info, c.CORR_EDGE_INFO_PATH)
        else:
            corr_edge_info = torch.load(c.CORR_EDGE_INFO_PATH)

        print('')

        # Set up the entire_data dictionary
        for edge_type in c.HETERO_EDGE_DICT.keys():

            node1_type, node2_type = c.HETERO_EDGE_DICT[edge_type]
            
            if edge_type == "corr":
                edge_index, observable, edge_attr, codeIDs_i, codeIDs_j = corr_edge_info
            else:
                edge_df = pd.read_parquet(get_parquet_path(edge_type))

                ### FILTERING
                edge_df = edge_df[edge_df["dateID"] <= c.MAX_DATEID]  # Filter by c.MAX_DATEID
                ###

                edge_index = edge_df[[f"{node1_type}_nodeID", f"{node2_type}_nodeID"]].values.T
                observable = edge_df["dateID"].values
                edge_attr  = np.ones(edge_index.shape[1], dtype=c.NP_FLOAT32)  # Placeholder for edge attributes
                codeIDs_i = edge_df[f"{node1_type}_codeID"].values
                codeIDs_j = edge_df[f"{node2_type}_codeID"].values

                del edge_df  # Free memory

            edge_type_id  = np.full(edge_index.shape[1], c.HETERO_EDGE_ID[edge_type],  dtype=c.NP_INT32)
            node_type_i   = np.full(edge_index.shape[1], c.HETERO_NODE_ID[node1_type], dtype=c.NP_INT32)
            node_type_j   = np.full(edge_index.shape[1], c.HETERO_NODE_ID[node2_type], dtype=c.NP_INT32)
                
            entire_edges[edge_type] = {
                'edge_index': edge_index,
                'observable': observable,
                'edge_attr': edge_attr,
                'edge_type': edge_type_id,
                'node_type_i': node_type_i,
                'node_type_j': node_type_j,
                'codeIDs_i': codeIDs_i,
                'codeIDs_j': codeIDs_j
            }
            print(f'Finished processing edge_type: {edge_type}')

        print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")

        for node_type in c.HETERO_NODE_TYPES:
            node_df = pd.read_parquet(get_parquet_path(node_type))
            node_nodeID = node_df.loc[:, "nodeID"].to_numpy(dtype=c.NP_INT32)
            node_codeID = node_df.loc[:, "codeID"].to_numpy(dtype=c.NP_INT32)
            node_dateID = node_df.loc[:, "dateID"].to_numpy(dtype=c.NP_INT32)
            node_features = node_df.values.astype(c.NP_FLOAT32)
            node_type_id = np.full(node_nodeID.shape[0], c.HETERO_NODE_ID[node_type], dtype=c.NP_FLOAT32)
            del node_df  # Free memory

            entire_nodes[node_type] = {
                'nodeID': node_nodeID,
                'codeID': node_codeID,
                'observable': node_dateID,
                'features': node_features,
                'node_type': node_type_id
            }
            print(f'Finished processing node_type: {node_type}')
        
        returns = pd.read_parquet(get_parquet_path(c.RETURN_FILE_ALIAS))
        set_labels(returns)  # Set labels for the returns DataFrame

        # Create HeteroData objects for each dateID
        for i, (dateID, tfID) in enumerate(dateID_to_tfid.items(), 1):
            if tfID < c.USE_MIN_TFID or tfID > c.USE_MAX_TFID:
                continue  # Skip dateIDs outside the specified range
            data = HeteroData()

            for edge_type, edge_info in entire_edges.items():
                edge_index   = edge_info['edge_index']  # shape: [2, num_edges]
                edge_attr    = edge_info['edge_attr']   # Edge thickness
                edge_type_id = edge_info['edge_type']   # Edge type ID
                node_type_i  = edge_info['node_type_i'] # Node type ID for source node
                node_type_j  = edge_info['node_type_j'] # Node type ID for target node
                codeIDs_i    = edge_info['codeIDs_i']   # Code IDs for source node
                codeIDs_j    = edge_info['codeIDs_j']   # Code IDs for target node
                observable   = edge_info['observable']  # Date IDs for edges

                node1_type, node2_type = c.HETERO_EDGE_DICT[edge_type]

                idx = np.where(observable == dateID)[0]
                data[node1_type, edge_type, node2_type].edge_index   = torch.as_tensor(edge_index[:, idx], dtype=c.TORCH_LONG).cpu()
                data[node1_type, edge_type, node2_type].edge_attr    = torch.as_tensor(edge_attr[idx]    , dtype=c.TORCH_FLOAT32).cpu()
                data[node1_type, edge_type, node2_type].edge_type_id = torch.as_tensor(edge_type_id[idx] , dtype=c.TORCH_INT32).cpu()
                data[node1_type, edge_type, node2_type].node_type_i  = torch.as_tensor(node_type_i[idx]  , dtype=c.TORCH_INT32).cpu()
                data[node1_type, edge_type, node2_type].node_type_j  = torch.as_tensor(node_type_j[idx]  , dtype=c.TORCH_INT32).cpu()
                data[node1_type, edge_type, node2_type].codeIDs_i    = torch.as_tensor(codeIDs_i[idx]    , dtype=c.TORCH_INT32).cpu()
                data[node1_type, edge_type, node2_type].codeIDs_j    = torch.as_tensor(codeIDs_j[idx]    , dtype=c.TORCH_INT32).cpu()

            # TODO: insert HGT-sampling here
            output_node_set = returns.loc[returns['dateID'] == dateID, 'codeID'].to_list()
            iter_OS = HGTsampling(data, output_node_set, L=2, n=20)

            # print("sampling result")
            # for node_type, sampled_codeIDs in iter_OS.items(): 
            #     print(node_type, len(sampled_codeIDs))

            for node_type, node_info in entire_nodes.items():
                codeID = node_info['codeID']
                observable = node_info['observable']
                features = node_info['features']
                node_type_id = node_info['node_type']

                if node_type == "stock":
                    target_codeID= returns.loc[returns['dateID'] == dateID, 'codeID']
                    assert isinstance(target_codeID, pd.Series), f"Expected target_codeID to be a numpy array, got {type(target_codeID)}"
                    target_idx = np.isin(codeID, target_codeID).astype(c.NP_INT32)
                    del target_codeID  # Free memory
                    data[node_type].target = torch.as_tensor(target_idx, dtype=c.TORCH_INT32).cpu()
                    data[node_type].labels = torch.as_tensor(returns.loc[returns['dateID'] == dateID, ['neg', 'neu', 'pos']].values, dtype=c.TORCH_FLOAT32).cpu()
                else:
                    target_idx = np.zeros(codeID.shape[0], dtype=c.NP_INT32)
                    data[node_type].target = torch.as_tensor(target_idx, dtype=c.TORCH_INT32).cpu()
                del target_idx  # Free memory

                using_codeIDs = iter_OS[node_type] if node_type in iter_OS else []
                mask_sampling = (observable == dateID) & (np.isin(codeID, using_codeIDs))

                data[node_type].codeID = torch.as_tensor(codeID[mask_sampling], dtype=c.TORCH_INT32).cpu()
                data[node_type].node_type = torch.as_tensor(node_type_id[mask_sampling], dtype=c.TORCH_INT32).cpu()

                if node_type in ["stock", "mktIdx", "future"]:
                    # LIMITING the features to the GRU_WINDOW_SIZE
                    mask_extract = (features[:, c.O_DATEID_COL_ID] == dateID) & (tfID - features[:, c.O_TFID_COL_ID] < c.GRU_WINDOW_SIZE)
                if node_type in ["statement"]:
                    # LIMITING the features to the NUM_OCCUR_WINDOW_SIZE
                    mask_extract = get_occurence_mask(nodeID_table, node_type, dateID, c.NUM_OCCUR_WINDOW_SIZE)

                mf = features[mask_extract]

                # for each codeID, thier sequential features are sorted by tfID
                # it use to get embedding from GRU or attention
                seq_list = []
                for cid in data[node_type].codeID.numpy():
                    mf_c = mf[mf[:, c.O_CODEID_COL_ID] == cid]
                    mf_c = mf_c[np.argsort(mf_c[:, c.O_TFID_COL_ID], kind="stable")]
                    seq_list.append(
                        torch.from_numpy(
                            np.ascontiguousarray(mf_c[:, c.O_MAINDATA_START_ID:], dtype=c.NP_FLOAT32)
                        )
                    )

                if seq_list:
                    data[node_type].x = pad_sequence(seq_list, batch_first=True, padding_value=0.0).cpu()
                    data[node_type].seq_len = torch.tensor([s.shape[0] for s in seq_list], dtype=c.TORCH_LONG).cpu()
                else:
                    data[node_type].x = torch.empty((0, 0, 0), dtype=c.TORCH_FLOAT32).cpu()
                    data[node_type].seq_len = torch.empty((0,), dtype=c.TORCH_LONG).cpu()
                
            torch.save(data, os.path.join(self.processed_dir, f'data_{dateID}.pt'))
            print(f'\rdateID: {dateID},  {i}/{len(dateIDs)}', end='')
        print("\nFinished processing all dateIDs.")

    def len(self):
        return len(self.processed_file_names)

    def get(self, tfID:int) -> HeteroData:
        """
        Get a HeteroData object by its TFID.
        """
        if tfID < c.USE_MIN_TFID or tfID > c.USE_MAX_TFID:
            raise IndexError("Index out of range")
    
        data_path = os.path.join(self.processed_dir, f'data_{tfID}.pt')
        data = torch.load(data_path)
        return data