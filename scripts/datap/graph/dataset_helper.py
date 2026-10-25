from typing import Any, Dict, List
from duckdb import DuckDBPyConnection as connect
from torch_geometric.data import HeteroData
import numpy as np
import pandas as pd
import torch
from torch.nn.utils.rnn import pad_sequence

import scripts.datap.graph.const as c

NECESSARY_COLUMNS_FOR_EDGES = ["tIDs", "attr", "etID"] # and "edge_index" will be added later
NECESSARY_COLUMNS_FOR_NODES = ["tIDs", "lnID", "gnID", "cIDs", "ntIDs"] # and "feats" will be added later

def _get_occurence_mask(df: pd.DataFrame, col: str, dateID: int, num_occur_window_size: int) -> pd.Series:
    df_o = df[(df['nodeType']==col)].sort_values(by=['dateID', 'codeID']).copy()
    df_o['current_num_occur'] = df_o['codeID'].map(
        df_o[df_o['dateID'] <= dateID]
        .sort_values(by=['dateID', 'codeID'])
        .groupby('codeID')['num_occur']
        .max()
    )
    df_o.loc[df_o['dateID'] > dateID, 'current_num_occur'] = np.nan
    df_o['num_occur'] = df_o['num_occur'] - (df_o['current_num_occur'] - (num_occur_window_size - 1))
    mask =  df_o['num_occur'].between(0, num_occur_window_size - 1) & df_o['codeID'].isin(df_o.loc[df_o['dateID'] == dateID, 'codeID'].unique())
    assert isinstance(mask, pd.Series), f"Expected mask to be a pandas Series, got {type(mask)}"
    del df_o  # Free memory
    return mask

def get_global_edges(con: connect, res: Dict[str, Any]) -> Dict[int, Any]:
    """`res` means result of `dataset.pre_process()` function."""
    global_edges: Dict[int, Any] = {}
    for i, (et, (tgt_nt, src_nt)) in enumerate(c.HETERO_EDGE_UNIT.items(), 1):
        etID = c.HETERO_EDGE_ID[et]
        if et == "corr":
            global_edges[etID] = {col: val for col, val in res.items()}
        else:
            edge_df = con.execute(f"SELECT * from edges.{et} where tID < {c.MAX_TID}").fetchdf()
            global_edges[etID] = {col: edge_df[col].copy() for col in NECESSARY_COLUMNS_FOR_EDGES}
            global_edges[etID]['edge_index'] = edge_df[
                [f"{tgt_nt}_lnID", f"{src_nt}_lnID"]
            ].iloc[:].T.copy()

        del edge_df  # Free memory
        print(f'-{i} edge_type: [{et}] is completed.')

    print("-> edge processing finished.\n")
    return global_edges


def get_global_nodes(con: connect) -> Dict[int, Any]:
    global_nodes: Dict[int, Any] = {}
    for i, nt in enumerate(c.HETERO_NODE_TYPES, 1):
        node_df = con.execute(f"SELECT * from nodes.{nt} where tID < {c.MAX_TID}").fetchdf()
        ntID = c.HETERO_NODE_ID[nt]
        global_nodes[ntID] = {col: node_df[col].copy() for col in NECESSARY_COLUMNS_FOR_NODES}
        global_nodes[ntID]['feats'] = node_df.iloc[:, c.NODE_FEATS_HEAD_IDX:].copy()

        del node_df  # Free memory
        print(f'-{i} node_type: [{nt}] is completed.')
    print("-> node processing finished.\n")
    return global_nodes



def set_edge_HeteroData(data: HeteroData, tID: int, global_edges: Dict[int, Any]) -> None:
    for etID, edge_info in global_edges.items():
        edge_index = edge_info['edge_index']  # shape: [2, num_edges]
        attr  = edge_info['attr']   # Edge thickness
        tIDs  = edge_info['tIDs']  # Date IDs for edges
        etIDs = edge_info['etIDs']  # Edge type IDs

        edgeNm = c.HETERO_EDGE_TYPES[etID]
        tgt_nodeNm, src_nodeNm = c.HETERO_EDGE_UNIT[edgeNm]
        idx = np.where(tIDs == tID)[0]
        data[tgt_nodeNm, edgeNm, src_nodeNm].edge_index = torch.as_tensor(edge_index[:, idx], dtype=c.TORCH_LONG).cpu()
        data[tgt_nodeNm, edgeNm, src_nodeNm].tIDs  = torch.as_tensor(tIDs[idx]  , dtype=c.TORCH_INT32).cpu()
        data[tgt_nodeNm, edgeNm, src_nodeNm].attr  = torch.as_tensor(attr[idx]  , dtype=c.TORCH_FLOAT32).cpu()
        data[tgt_nodeNm, edgeNm, src_nodeNm].etIDs = torch.as_tensor(etIDs[idx] , dtype=c.TORCH_INT32).cpu()




def set_node_HeteroData(data: HeteroData, tID: int, global_nodes: Dict[int, Any], node_tools: pd.DataFrame) -> None:
    for ntID, node_info in global_nodes.items():
        cIDs : pd.Series    = node_info['cIDs']
        tIDs : pd.Series    = node_info['tIDs']
        lnIDs: pd.Series    = node_info['lnID']
        feats: pd.DataFrame = node_info['feats']
        ntIDs: pd.Series    = node_info['ntIDs']

        # IMPORTANT: Ensure that lnIDs are consecutive integers for each node type
        assert sum(lnIDs[t] - (lnIDs[t-1] + 1) for t in range(1, len(lnIDs))) == 0, "lnIDs should be consecutive integers"
        assert len(cIDs) == len(tIDs) == len(lnIDs) == len(ntIDs) == feats.shape[0], "Mismatch in lengths of node attributes"

        nodeType = c.HETERO_NODE_TYPES[ntID]

        data[nodeType].lnIDs = torch.as_tensor(lnIDs, dtype=c.TORCH_INT32).cpu()
        data[nodeType].ntIDs = torch.as_tensor(ntIDs, dtype=c.TORCH_INT32).cpu()

        if nodeType in ["stock", "mktIdx", "future"]:
            # LIMITING the features to the GRU_WINDOW_SIZE
            mask_extract = (feats[:, c.O_TID_COL_ID] <= tID) & (tID - feats[:, c.O_TID_COL_ID] < c.GRU_WINDOW_SIZE)
        if nodeType in ["statement"]:
            # LIMITING the features to the NUM_OCCUR_WINDOW_SIZE
            mask_extract = _get_occurence_mask(node_tools, nodeType, tID, c.NUM_OCCUR_WINDOW_SIZE)

        masked_feats = feats[mask_extract]

        # for each codeID, thier sequential features are sorted by tfID
        # it use to get embedding from GRU or attention
        seq_list = []
        for lnID in data[nodeType].lnIDs.numpy():
            masked_feats_ln = masked_feats[masked_feats[:, c.O_CODEID_COL_ID] == lnID]
            masked_feats_ln = masked_feats_ln[np.argsort(masked_feats_ln[:, c.O_TID_COL_ID], kind="stable")]
            seq_list.append(
                torch.from_numpy(
                    np.ascontiguousarray(masked_feats_ln[:, c.O_MAINDATA_START_ID:], dtype=c.NP_FLOAT32)
                )
            )

        if seq_list:
            data[nodeType].x = pad_sequence(seq_list, batch_first=True, padding_value=0.0).cpu()
            data[nodeType].seq_len = torch.tensor([s.shape[0] for s in seq_list], dtype=c.TORCH_LONG).cpu()
        else:
            data[nodeType].x = torch.empty((0, 0, 0), dtype=c.TORCH_FLOAT32).cpu()
            data[nodeType].seq_len = torch.empty((0,), dtype=c.TORCH_LONG).cpu()