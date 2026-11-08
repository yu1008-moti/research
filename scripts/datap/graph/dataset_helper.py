from typing import Any, Dict, List
from duckdb import DuckDBPyConnection as connect
from torch_geometric.data import HeteroData
import numpy as np
import pandas as pd
import torch
from torch.nn.utils.rnn import pad_sequence

import scripts.datap.graph.const as c

GREEN = '\033[92m'
MAGENTA = '\033[95m'
END = '\033[0m'


def get_tIDs(conn: connect) -> np.ndarray:
    print("\rFetching tIDs", end="")
    tIDs = conn.execute(c.GET_TID_QUERY).df()['tID'].to_numpy()
    print(f"{GREEN}Fetched {len(tIDs)} tIDs from the database.{END}")
    return tIDs


def get_node_data_master(conn: connect) -> Dict[str, pd.DataFrame]:
    print("\rcreating node_data_master", end=" ")
    node_data_master = {ntNm: conn.execute(c.GET_NODE_DATA_MASTER_QUERY.substitute(ntNm=ntNm)).df() for ntNm in c.HETERO_NODE_TYPES}
    print(f"{GREEN}Node data for all node types was loaded successfully.{END}")
    return node_data_master


def set_edges(conn: connect, tID: int, data: HeteroData, pre_process_results: Dict[str, Any]) -> None:
    for etNm, (src_ntNm, tgt_ntNm) in c.HETERO_EDGE_UNIT.items():
        if etNm == "corr":
            # Use the pre-processed correlation edge data
            mask = pre_process_results['tID'] == tID
            edge_index = torch.tensor(pre_process_results['edge_index'][:, mask], dtype=torch.long)
            etIDs      = torch.tensor(pre_process_results['etID'][mask], dtype=torch.int16)
        else:
            edges_df = conn.execute(c.SET_EDGES_QUERY.substitute(src_ntNm=src_ntNm, tgt_ntNm=tgt_ntNm, etNm=etNm, tID=tID)).df()
            edge_index = torch.tensor(edges_df[[f"{src_ntNm}_lnID", f"{tgt_ntNm}_lnID"]].values.T, dtype=torch.long)
            etIDs = torch.tensor(np.full((edges_df.shape[0],), c.HETERO_EDGE_ID[etNm], dtype=c.NP_INT32))
        data[src_ntNm, etNm, tgt_ntNm].edge_index = edge_index
        data[src_ntNm, etNm, tgt_ntNm].etID = etIDs


def set_nodes(conn: connect, tID: int, data: HeteroData, nodeDataMaster: Dict[str, pd.DataFrame]):
    for ntNm, ntID in c.HETERO_NODE_ID.items():
        nodeData = nodeDataMaster[ntNm]
        cond = "=" if ntNm != "statement" else "<="
        seq_df = conn.execute(c.SET_NODES_QUERY.substitute(ntID=ntID, tID=tID, cond=cond)).df().set_index(['gnID'], drop=True)
        nodeData_gnID = nodeData.set_index('gnID', drop=False)
        nodeData_gnID = nodeData_gnID[~nodeData_gnID.index.duplicated(keep='first')] # for statement nodes
        x = nodeData[nodeData['tID'] == tID].set_index('gnID', drop=False).sort_values(by='lnID')
        X = []
        for seq in seq_df.loc[x['gnID'], 'seq'].to_numpy():
            assert isinstance(seq, np.ndarray), f"Expected seq to be a numpy array, but got {type(seq)}"
            x_seq_data = nodeData_gnID.loc[seq, :].iloc[:, c.NODE_FEATS_HEAD_IDX:].to_numpy()
            X.append(torch.tensor(x_seq_data, dtype=torch.float32))
        
        data[ntNm].x    = pad_sequence(X, batch_first=True, padding_value=0.0)
        data[ntNm].gnID = torch.tensor(x['gnID'].to_numpy(), dtype=torch.int32)
        data[ntNm].lnID = torch.tensor(x['lnID'].to_numpy(), dtype=torch.int16)
        data[ntNm].ntID = torch.tensor(x['ntID'].to_numpy(), dtype=torch.int16)

        del x, X, nodeData, nodeData_gnID  # Free memory
    del seq_df  # Free memory



def set_labels(conn: connect) -> None:
    returns = conn.execute("SELECT * from label.nxri;").df()

    train_mask = returns['tID'].between(c.TRAIN_RANGE_BY_DATEID[0], c.TRAIN_RANGE_BY_DATEID[1])
    define_labels_samples = returns[train_mask]
    num_define_labels_samples = len(define_labels_samples)

    q1 = int(num_define_labels_samples*1/3)
    q2 = int(num_define_labels_samples*2/3)

    sorted_returns = define_labels_samples.sort_values(by='NxRi')
    low_threshold = sorted_returns.iloc[q1]['NxRi']
    high_threshold = sorted_returns.iloc[q2]['NxRi']

    returns['neg'] = (returns['NxRi'] < low_threshold).astype(int)
    returns['pos'] = (returns['NxRi'] > high_threshold).astype(int)
    returns['neu'] = ((returns['NxRi'] >= low_threshold) & (returns['NxRi'] <= high_threshold)).astype(int)

    print(f"\n{MAGENTA}REPORT: Labeling of returns based on thresholds{END}")
    print(f"Number of samples used to define thresholds: {num_define_labels_samples}")
    print(f"Label thresholds   : low={low_threshold}, high={high_threshold}")
    print(f"Label distribution : neg={returns['neg'].sum()}, pos={returns['pos'].sum()}, neu={returns['neu'].sum()}")
    print(f'(%) neg : neu : pos = {returns["neg"].sum()/len(returns):.5%} : {returns["neu"].sum()/len(returns):.5%} : {returns["pos"].sum()/len(returns):.5%}\n')