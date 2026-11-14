from typing import Any, Dict, List
from duckdb import DuckDBPyConnection as connect
from torch_geometric.data import HeteroData
import numpy as np
import pandas as pd
import torch
from torch.nn.utils.rnn import pad_sequence
from datetime import datetime as dt
import os

import scripts.datap.graph.const as c

GREEN = '\033[92m'
MAGENTA = '\033[95m'
CYAN = '\033[96m'
END = '\033[0m'


class NodeDataMaster:
    def __init__(self, conn: connect):
        self.conn = conn
        self.node_data_master = self._create_node_data_master()
        print(f"[{GREEN}Node data for all node types was loaded successfully{END}]")

    def _create_node_data_master(self) -> List[pd.DataFrame]:
        print("\rCreating node_data_master", end=" ")
        return [
            self.conn.execute(c.GET_NODE_DATA_MASTER_QUERY.substitute(ntNm=ntNm)).df().set_index('gnID', drop=False)
            for ntNm in c.HETERO_NODE_TYPES
        ]


def get_tIDs(conn: connect) -> np.ndarray:
    print("\rFetching tIDs", end=" ")
    tIDs = conn.execute(c.GET_TID_QUERY).df()['tID'].to_numpy()
    print(f"[{GREEN}Fetched {len(tIDs)} tIDs from the database{END}]")
    return tIDs


def set_edges(conn: connect, tID: int, data: HeteroData, pre_process_results: Dict[str, Any]) -> None:
    for etNm, (src_ntNm, tgt_ntNm) in c.HETERO_EDGE_UNIT.items():
        if etNm == "corr":
            mask = pre_process_results['tID'] == tID
            edge_index = torch.tensor(pre_process_results['edge_index'][:, mask], dtype=torch.long)
            etIDs      = torch.tensor(pre_process_results['etID'][mask], dtype=torch.int16)
        else:
            edges_df = conn.execute(c.SET_EDGES_QUERY.substitute(src_ntNm=src_ntNm, tgt_ntNm=tgt_ntNm, etNm=etNm, tID=tID)).df()
            edge_index = torch.tensor(edges_df[[f"{src_ntNm}_lnID", f"{tgt_ntNm}_lnID"]].values.T, dtype=torch.long)
            etIDs = torch.tensor(np.full((edges_df.shape[0],), c.HETERO_EDGE_ID[etNm], dtype=c.NP_INT32))
        data[src_ntNm, etNm, tgt_ntNm].edge_index = edge_index
        data[src_ntNm, etNm, tgt_ntNm].etID = etIDs


def set_nodes(conn: connect, tID: int, data: HeteroData, nodeDataMaster: NodeDataMaster, returns: pd.DataFrame) -> None:
    seq_df = conn.execute(c.SET_NODES_QUERY.substitute(tID=tID)).df().set_index(['gnID'], drop=True)
    for (ntNm, ntID), nodeData in zip(c.HETERO_NODE_ID.items(), nodeDataMaster.node_data_master):
        x = nodeData[nodeData['tID'] == tID].sort_values(by='lnID')
        nodeData_gnID = nodeData[~nodeData.index.duplicated(keep='first')] # for statement nodes
        X, seq_len_list = [], []

        for seq, seq_len in seq_df[seq_df['ntID'] == ntID].loc[x['gnID'], ['seq', 'seq_len']].to_numpy():
            assert isinstance(seq, np.ndarray), f"Expected seq to be a numpy array, but got {type(seq)}"
            x_seq_data = nodeData_gnID.loc[seq, :].iloc[:, c.NODE_FEATS_HEAD_IDX:].to_numpy()
            X.append(torch.tensor(x_seq_data, dtype=torch.float32))
            seq_len_list.append(seq_len)

        if ntNm == "stock":
            returns_tID = returns[returns['tID'] == tID].sort_values(by='lnID')
            isTarget = x['lnID'].isin(returns_tID['lnID']).astype(np.int8)
            data[ntNm].target = torch.tensor(isTarget.to_numpy(), dtype=torch.int8)
            data[ntNm].labels = torch.tensor(returns_tID[['neg', 'neu', 'pos']].to_numpy(), dtype=torch.int8)

        data[ntNm].x       = pad_sequence(X, batch_first=True, padding_value=0.0)
        data[ntNm].seq_len = torch.tensor(seq_len_list, dtype=torch.int32)
        data[ntNm].gnID    = torch.tensor(x['gnID'].to_numpy(), dtype=torch.int32)
        data[ntNm].lnID    = torch.tensor(x['lnID'].to_numpy(), dtype=torch.int16)
        data[ntNm].ntID    = torch.tensor(x['ntID'].to_numpy(), dtype=torch.int16)
        del x, X, nodeData, nodeData_gnID  # Free memory
    del seq_df  # Free memory


def get_labels(conn: connect) -> pd.DataFrame:
    returns = conn.execute("SELECT * from label.nxri;").df()
    return returns

def check_lnIDs_constraint(processed_dir: str) -> bool:
    start_time = dt.now()
    print(f"{CYAN}Checking graph data for consecutive lnIDs for tIDs in range [{c.USE_MIN_TID}, {c.USE_MAX_TID}]{END}")
    for tID in range(c.USE_MIN_TID, c.USE_MAX_TID + 1):
        data = torch.load(os.path.join(processed_dir, f'data_{tID}.pt'), weights_only=False)
        lnIDs = torch.cat([data[nt].lnID for nt in c.HETERO_NODE_TYPES], dim=0).to(c.DEVICE)
        assert sum(lnIDs[1:] - lnIDs[:-1] != 1) == 0, f"{MAGENTA}Graph data for tID {tID} is not consecutive. Found non-consecutive lnIDs: {lnIDs[1:] - lnIDs[:-1]}{END}"
        print(f"\r[{(tID - c.USE_MIN_TID + 1):4d}/{(c.USE_MAX_TID + 1)-c.USE_MIN_TID}] Processed tID: {tID}", end=" ")
    end_time = dt.now()
    print(f"[{GREEN}Graph consecutive check completed in: {end_time - start_time}{END}]")
    return True


def set_labels(returns: pd.DataFrame) -> None:

    train_mask = returns['tID'].between(c.TRAIN_RANGE_TID[0], c.TRAIN_RANGE_TID[1])
    define_labels_samples = returns[train_mask]
    num_define_labels_samples = len(define_labels_samples)

    q1, q2 = int(num_define_labels_samples*1/3), int(num_define_labels_samples*2/3)

    sorted_returns = define_labels_samples.sort_values(by='NxRi')
    low_threshold, high_threshold = sorted_returns.iloc[q1]['NxRi'], sorted_returns.iloc[q2]['NxRi']

    returns['neg'] = (returns['NxRi'] < low_threshold).astype(int)
    returns['pos'] = (returns['NxRi'] > high_threshold).astype(int)
    returns['neu'] = ((returns['NxRi'] >= low_threshold) & (returns['NxRi'] <= high_threshold)).astype(int)

    print(f"\n{CYAN}REPORT: Labeling of returns based on thresholds{END}")
    print(f"Number of samples used to define thresholds: {num_define_labels_samples}")
    print(f"Label thresholds   : low={low_threshold}, high={high_threshold}")
    print(f"Label distribution : neg={returns['neg'].sum()}, pos={returns['pos'].sum()}, neu={returns['neu'].sum()}")
    print(f'(%) neg : neu : pos = {returns["neg"].sum()/len(returns):.5%} : {returns["neu"].sum()/len(returns):.5%} : {returns["pos"].sum()/len(returns):.5%}\n')