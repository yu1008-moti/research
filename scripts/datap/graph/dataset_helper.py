from typing import Any, Dict, List
from duckdb import DuckDBPyConnection as connect
from torch_geometric.data import HeteroData
import numpy as np
import pandas as pd
import torch
from torch.nn.utils.rnn import pad_sequence

import scripts.datap.graph.const as c


def get_tIDs(conn: connect) -> np.ndarray:
    print("Fetching tIDs from the database...")
    tIDs = conn.execute(
        f"""
            select tID
            from act.tools.date_tool
            where tID between {c.USE_MIN_TFID} and {c.USE_MAX_TFID}
            order by tID;
        """
    ).df()['tID'].to_numpy()
    print(f"Fetched {len(tIDs)} tIDs from the database.")
    return tIDs


def get_node_data_master(conn: connect) -> Dict[str, pd.DataFrame]:
    print("creating node_data_master for all node types...")
    node_data_master = {
        nodeTypeName: conn.execute(
            f"""
                select *
                from act.nodes.{nodeTypeName}
                order by gnID;
            """
        ).df()
        for nodeTypeName in c.HETERO_NODE_TYPES
    }
    print("Node data for all node types was loaded successfully.\n")
    return node_data_master


def set_edges(conn: connect, tID: int, data: HeteroData, pre_process_results: Dict[str, Any]) -> None:
    for edgeTypeName, (src_nodeTypeName, tgt_nodeTypeName) in c.HETERO_EDGE_UNIT.items():
        if edgeTypeName == "corr":
            # Use the pre-processed correlation edge data
            mask = pre_process_results['tID'] == tID
            edge_index = torch.tensor(pre_process_results['edge_index'][:, mask], dtype=torch.long)
            etIDs      = torch.tensor(pre_process_results['etID'][mask], dtype=torch.int16)
        else:
            edges_df = conn.execute(
                f"""
                    select {src_nodeTypeName}_lnID, {tgt_nodeTypeName}_lnID
                    from act.edges.{edgeTypeName}
                    where tID = {tID}
                    order by {src_nodeTypeName}_gnID, {tgt_nodeTypeName}_gnID;
                """
            ).df()
            edge_index = torch.tensor(
                edges_df[[f"{src_nodeTypeName}_lnID", f"{tgt_nodeTypeName}_lnID"]].values.T, 
                dtype=torch.long
            )
            etIDs = torch.tensor(np.full((edges_df.shape[0],), c.HETERO_EDGE_ID[edgeTypeName], dtype=c.NP_INT32))
        data[src_nodeTypeName, edgeTypeName, tgt_nodeTypeName].edge_index = edge_index
        data[src_nodeTypeName, edgeTypeName, tgt_nodeTypeName].etID = etIDs



def set_nodes(conn: connect, tID: int, data: HeteroData, nodeDataMaster: Dict[str, pd.DataFrame]):
    seq_df = conn.execute(
        f"""
            select gnID, seq
            from act.sequence.node
            where tID = {tID}
        """
    ).df().set_index(['gnID'], drop=True)
    for nodeTypeName in c.HETERO_NODE_TYPES:
        nodeData = nodeDataMaster[nodeTypeName].set_index('gnID', drop=False)
        x = nodeData.loc[nodeData['tID'] == tID]
        gnIDs = x['gnID']
        X = []
        for seq in seq_df.loc[gnIDs, 'seq'].to_numpy():
            assert isinstance(seq, np.ndarray), f"Expected seq to be a numpy array, but got {type(seq)}"
            x_seq_data = nodeData.loc[seq, :].iloc[:, c.NODE_FEATS_HEAD_IDX:].to_numpy()
            X.append(torch.tensor(x_seq_data, dtype=torch.float32))
        
        data[nodeTypeName].x    = pad_sequence(X, batch_first=True, padding_value=0.0)
        data[nodeTypeName].gnID = torch.tensor(gnIDs.to_numpy(), dtype=torch.int32)
        data[nodeTypeName].lnID = torch.tensor(x['lnID'].to_numpy(), dtype=torch.int16)
        data[nodeTypeName].ntID = torch.tensor(x['ntID'].to_numpy(), dtype=torch.int16)

        del x, gnIDs, X  # Free memory
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

    print("\nREPORT: Labeling of returns based on thresholds")
    print(f"Number of samples used to define thresholds: {num_define_labels_samples}")
    print(f"Label thresholds   : low={low_threshold}, high={high_threshold}")
    print(f"Label distribution : neg={returns['neg'].sum()}, pos={returns['pos'].sum()}, neu={returns['neu'].sum()}")
    print(f'(%) neg : neu : pos = {returns["neg"].sum()/len(returns):.5%} : {returns["neu"].sum()/len(returns):.5%} : {returns["pos"].sum()/len(returns):.5%}\n')