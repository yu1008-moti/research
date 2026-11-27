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
            _etNm = etNm.replace("reverse_", "")
            edges_df = conn.execute(c.SET_EDGES_QUERY.substitute(src_ntNm=src_ntNm, tgt_ntNm=tgt_ntNm, etNm=_etNm, tID=tID)).df()
            edge_index = torch.tensor(edges_df[[f"{src_ntNm}_lnID", f"{tgt_ntNm}_lnID"]].values.T, dtype=torch.long)
            etIDs = torch.tensor(np.full((edges_df.shape[0],), c.HETERO_EDGE_ID[etNm], dtype=c.NP_INT32))
        data[src_ntNm, etNm, tgt_ntNm].edge_index = edge_index
        data[src_ntNm, etNm, tgt_ntNm].etID = etIDs
    
def remove_outliers(returns_tID: pd.DataFrame) -> pd.DataFrame:
    rm_ratio = c.OUTLIER_REMOVE_RATIO
    returns_tID = returns_tID.sort_values(by='NxRi')
    returns_tID = returns_tID.iloc[int(len(returns_tID) * rm_ratio): int(len(returns_tID) * (1 - rm_ratio))]
    return returns_tID.sort_values(by='lnID')


def annotation(returns_tID: pd.DataFrame, is_train: bool, ds_root: str) -> pd.DataFrame:
    returns_tID = returns_tID.copy()
    use, comp = ds_root.split('_')
    
    if is_train:
        returns_tID['neg'] = (returns_tID[use] <  0).astype(np.int8) if comp == 'zero' else (returns_tID[use] <  returns_tID[comp]).astype(np.int8)
    else:
        returns_tID['neg'] = (returns_tID[use] <= 0).astype(np.int8) if comp == 'zero' else (returns_tID[use] <= returns_tID[comp]).astype(np.int8)
    returns_tID['pos'] = (returns_tID[use] >  0).astype(np.int8) if comp == 'zero' else (returns_tID[use] >  returns_tID[comp]).astype(np.int8)
    
    # assert (returns_tID['neg'] + returns_tID['pos'] == 1).all(), f"Labeling error: Some rows in returns_tID have neither 'neg' nor 'pos' label set to 1."
    return returns_tID


def balance_classes(returns_tID: pd.DataFrame) -> pd.DataFrame:
    """多数派クラスをランダムにアンダーサンプリングし, 各クラスの件数を最少クラスに揃える (lnID 順を維持)."""
    labels = c.CLASS_LABELS
    min_num_class = int(returns_tID[labels].sum(axis=0).min())
    keep = [
        returns_tID[returns_tID[lb] == 1].sample(n=min_num_class, replace=False).index
        for lb in labels
    ]
    return returns_tID.loc[returns_tID.index.isin(np.concatenate(keep))].sort_values(by='lnID')



def set_nodes(conn: connect, tID: int, data: HeteroData, nodeDataMaster: NodeDataMaster, returns: pd.DataFrame, ds_root: str) -> None:
    seq_df = conn.execute(c.SET_NODES_QUERY.substitute(tID=tID)).df().set_index(['gnID'], drop=True)
    for (ntNm, ntID), nodeData in zip(c.HETERO_NODE_ID.items(), nodeDataMaster.node_data_master):
        x = nodeData[nodeData['tID'] == tID].sort_values(by='lnID')
        nodeData_gnID = nodeData[~nodeData.index.duplicated(keep='first')] # for statement nodes
        X, seq_len_list = [], []

        for seq, seq_len in seq_df[seq_df['ntID'] == ntID].loc[x['gnID'], ['seq', 'seq_len']].to_numpy():
            assert isinstance(seq, np.ndarray), f"Expected seq to be a numpy array, but got {type(seq)}"
            x_seq_data = nodeData_gnID.loc[seq, :].iloc[:, c.NODE_FEATS_HEAD_IDX:].to_numpy()
            x_seq_data = np.nan_to_num(x_seq_data, nan=0.0)  # Replace NaN with 0.0
            X.append(torch.tensor(x_seq_data, dtype=torch.float32))
            seq_len_list.append(seq_len)

        if ntNm == "stock":
            # TRAIN_SPLIT は index 空間 (tID - _BASE), 上限は exclusive (= VALID_SPLIT の開始)
            is_train = c.TRAIN_SPLIT[0][0] <= tID - c._BASE < c.TRAIN_SPLIT[0][1] # if you want to change condition, you can change it ./const.py
            returns_tID = returns[returns['tID'] == tID].sort_values(by='lnID')
            if is_train:
                returns_tID = remove_outliers(returns_tID)  # 未来情報 (NxRi) を使うので学習期間のみ
            returns_tID = annotation(returns_tID, is_train, ds_root)  # ラベル付与
            if is_train:
                returns_tID = balance_classes(returns_tID)
            isTarget = x['lnID'].isin(returns_tID['lnID']).astype(np.int8)
            assert int(isTarget.sum()) == len(returns_tID), f"Mismatch between target and labels for tID {tID} in stock node type."
            data[ntNm].target  = torch.tensor(isTarget.to_numpy(), dtype=torch.int8)
            data[ntNm].labels  = torch.tensor(returns_tID[c.CLASS_LABELS].to_numpy(), dtype=torch.int8)
            data[ntNm].returns = torch.tensor(returns_tID[['NxRi']].to_numpy(), dtype=torch.float32)

        data[ntNm].x       = pad_sequence(X, batch_first=True, padding_value=0.0)
        data[ntNm].seq_len = torch.tensor(seq_len_list, dtype=torch.int32)
        data[ntNm].gnID    = torch.tensor(x['gnID'].to_numpy(), dtype=torch.int32)
        data[ntNm].lnID    = torch.tensor(x['lnID'].to_numpy(), dtype=torch.int16)
        data[ntNm].ntID    = torch.tensor(x['ntID'].to_numpy(), dtype=torch.int16)
        del x, X, nodeData, nodeData_gnID  # Free memory
    del seq_df  # Free memory


def get_labels(conn: connect) -> pd.DataFrame:
    returns = conn.execute("SELECT * from label.nxri;").df()
    returns = returns.dropna()
    returns = returns.sort_values(by=['tID', 'lnID']).reset_index(drop=True)
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