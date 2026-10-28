from typing import Any, Dict, List
from duckdb import DuckDBPyConnection as connect
from torch_geometric.data import HeteroData
import numpy as np
import pandas as pd
import torch
from torch.nn.utils.rnn import pad_sequence

import scripts.datap.graph.const as c

NECESSARY_COLUMNS_FOR_EDGES = ["tID", "attr", "etID"] # and "edge_index" will be added later
NECESSARY_COLUMNS_FOR_NODES = ["tID", "lnID", "gnID", "cID", "ntID"] # and "feats" will be added later

def _get_occurence_mask(df: pd.DataFrame, ntID: int, dateID: int, occur_num_window_size: int) -> pd.Series:
    df_o = df[(df['ntID']==ntID)].sort_values(by=['tID', 'cID']).copy()
    df_o['current_occur_num'] = df_o['cID'].map(
        df_o[df_o['tID'] <= dateID]
        .sort_values(by=['tID', 'cID'])
        .groupby('cID')['occur_num']
        .max()
    )
    df_o.loc[df_o['tID'] > dateID, 'current_occur_num'] = np.nan
    df_o['occur_num'] = df_o['occur_num'] - (df_o['current_occur_num'] - (occur_num_window_size - 1))
    mask =  df_o['occur_num'].between(0, occur_num_window_size - 1) & df_o['cID'].isin(df_o.loc[df_o['tID'] == dateID, 'cID'].unique())
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
            edge_df = con.execute(f"SELECT * from edges.{et} where tID < {c.MAX_TID};").df()
            global_edges[etID] = {col: edge_df[col].to_numpy() for col in NECESSARY_COLUMNS_FOR_EDGES}
            global_edges[etID]['edge_index'] = edge_df[
                [f"{tgt_nt}_lnID", f"{src_nt}_lnID"]
            ].iloc[:].T.to_numpy(dtype=c.NP_FLOAT32)  # shape: [2, num_edges]
            del edge_df  # Free memory
        print(f'[{i}/{len(c.HETERO_EDGE_UNIT)}] edge_type[{et}] is completed.')

    print("-> edge processing finished.\n")
    return global_edges


def get_global_nodes(con: connect) -> Dict[int, Any]:
    global_nodes: Dict[int, Any] = {}
    for i, nt in enumerate(c.HETERO_NODE_TYPES, 1):
        node_df = con.execute(f"SELECT * from nodes.{nt} where tID < {c.MAX_TID};").df()
        ntID = c.HETERO_NODE_ID[nt]
        global_nodes[ntID] = {col: node_df[col].to_numpy() for col in NECESSARY_COLUMNS_FOR_NODES}
        global_nodes[ntID]['feats'] = node_df.iloc[:, c.NODE_FEATS_HEAD_IDX:].to_numpy(dtype=c.NP_FLOAT32)  # shape: [num_nodes, num_feats]

        del node_df  # Free memory
        print(f'[{i}/{len(c.HETERO_NODE_TYPES)}] node_type[{nt}] is completed.')
    print("-> node processing finished.\n")
    return global_nodes



def set_edge_HeteroData(data: HeteroData, tID: int, global_edges: Dict[int, Any]) -> None:
    for i, (etID, edge_info) in enumerate(global_edges.items(), 1):
        edge_index: np.ndarray = edge_info['edge_index']  # shape: [2, num_edges]
        attr      : np.ndarray = edge_info['attr'] # Edge thickness
        tIDs      : np.ndarray = edge_info['tID']  # Date IDs for edges
        etIDs     : np.ndarray = edge_info['etID'] # Edge type IDs

        edgeNm = c.HETERO_EDGE_TYPES[etID]
        tgt_nodeNm, src_nodeNm = c.HETERO_EDGE_UNIT[edgeNm]
        idx = np.where(tIDs == tID)[0]
        data[tgt_nodeNm, edgeNm, src_nodeNm].edge_index = torch.from_numpy(edge_index[:, idx].copy()).cpu()
        data[tgt_nodeNm, edgeNm, src_nodeNm].tIDs       = torch.from_numpy(tIDs[idx].copy() ).cpu()
        data[tgt_nodeNm, edgeNm, src_nodeNm].attr       = torch.from_numpy(attr[idx].copy() ).cpu()
        data[tgt_nodeNm, edgeNm, src_nodeNm].etIDs      = torch.from_numpy(etIDs[idx].copy()).cpu()


def set_node_HeteroData(data: HeteroData, tID: int, global_nodes: Dict[int, Any], node_tools: pd.DataFrame) -> None:
    for ntID, node_info in global_nodes.items():
        cIDs : np.ndarray   = node_info['cID']
        tIDs : np.ndarray   = node_info['tID']
        lnIDs: np.ndarray   = node_info['lnID']
        feats: pd.DataFrame = node_info['feats']
        ntIDs: np.ndarray   = node_info['ntID']

        # IMPORTANT: Ensure that lnIDs are consecutive integers for each node type
        # assert sum(lnIDs[t] - (lnIDs[t-1] + 1) for t in range(1, len(lnIDs))) == 0, "lnIDs should be consecutive integers"
        # assert len(cIDs) == len(tIDs) == len(lnIDs) == len(ntIDs) == feats.shape[0], "Mismatch in lengths of node attributes"

        idx = np.where(tIDs == tID)[0]
        nodeType = c.HETERO_NODE_TYPES[ntID]

        data[nodeType].lnIDs = torch.from_numpy(lnIDs).cpu()
        data[nodeType].ntIDs = torch.from_numpy(ntIDs).cpu()

        if nodeType in ["stock", "mktidx", "future"]:
            # LIMITING the features to the GRU_WINDOW_SIZE
            mask = (tIDs <= tID) & (tID - tIDs < c.GRU_WINDOW_SIZE)
        if nodeType in ["statement"]:
            # LIMITING the features to the NUM_OCCUR_WINDOW_SIZE
            mask = _get_occurence_mask(node_tools, ntID, tID, c.NUM_OCCUR_WINDOW_SIZE)

        masked_feats = feats[mask]

        # for each codeID, thier sequential features are sorted by tfID
        # it use to get embedding from GRU or attention
        seq_list = []
        for lnID in lnIDs[idx]:
            masked_feats_ln = masked_feats[lnIDs[mask] == lnID]
            masked_feats_ln = masked_feats_ln[np.argsort(tIDs[mask][lnIDs[mask] == lnID], kind="stable")]
            seq_list.append(
                torch.from_numpy(
                    np.ascontiguousarray(masked_feats_ln, dtype=c.NP_FLOAT32)
                )
            )

        if seq_list:
            data[nodeType].x = pad_sequence(seq_list, batch_first=True, padding_value=0.0).cpu()
            data[nodeType].seq_len = torch.tensor([s.shape[0] for s in seq_list], dtype=c.TORCH_LONG).cpu()
        else:
            data[nodeType].x = torch.empty((0, 0, 0), dtype=c.TORCH_FLOAT32).cpu()
            data[nodeType].seq_len = torch.empty((0,), dtype=c.TORCH_LONG).cpu()


def set_labels(return_df: pd.DataFrame) -> None:

    train_mask = return_df['tID'].between(c.TRAIN_RANGE_BY_DATEID[0], c.TRAIN_RANGE_BY_DATEID[1])
    define_labels_samples = return_df[train_mask]
    num_define_labels_samples = len(define_labels_samples)

    q1 = int(num_define_labels_samples*1/3)
    q2 = int(num_define_labels_samples*2/3)

    sorted_returns = define_labels_samples.sort_values(by='NxRi')
    low_threshold = sorted_returns.iloc[q1]['NxRi']
    high_threshold = sorted_returns.iloc[q2]['NxRi']

    return_df['neg'] = (return_df['NxRi'] < low_threshold).astype(int)
    return_df['pos'] = (return_df['NxRi'] > high_threshold).astype(int)
    return_df['neu'] = ((return_df['NxRi'] >= low_threshold) & (return_df['NxRi'] <= high_threshold)).astype(int)

    print("\nREPORT: Labeling of returns based on thresholds")
    print(f"Number of samples used to define thresholds: {num_define_labels_samples}")
    print(f"Label thresholds   : low={low_threshold}, high={high_threshold}")
    print(f"Label distribution : neg={return_df['neg'].sum()}, pos={return_df['pos'].sum()}, neu={return_df['neu'].sum()}")
    print(f'(%) neg : neu : pos = {return_df["neg"].sum()/len(return_df):.5%} : {return_df["neu"].sum()/len(return_df):.5%} : {return_df["pos"].sum()/len(return_df):.5%}\n')