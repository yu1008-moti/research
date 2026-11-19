from torch_geometric.data import HeteroData
from collections import defaultdict
from typing import List, Dict
import torch
import numpy as np
from pprint import pprint

import scripts.datap.graph.const as c


T, S = 0, 1  # T: target node, S: source node
NodeTypeID = int
TargetNodeTypeID = NodeTypeID
EdgeTypeID = int
SourceNodeTypeID = NodeTypeID
TargetCodeID  = int
SourceCodeID  = int
SourceCodeIDs = List[SourceCodeID]
AdjacencyMatrix = Dict[SourceNodeTypeID, Dict[EdgeTypeID, Dict[TargetNodeTypeID, Dict[TargetCodeID, SourceCodeIDs]]]]

NormalizedDegreeScore = float
Budget = Dict[SourceNodeTypeID, Dict[SourceCodeID, NormalizedDegreeScore]]

SampledNodeCodeID = int
SampledNodeTypeID = int

NeighborSet = Dict[SampledNodeTypeID, List[SampledNodeCodeID]]
OutputSet   = Dict[SampledNodeTypeID, List[SampledNodeCodeID]]


INIT_OS_KEY = 0
    

__all__ = ['HGTsampling']

def str2id(ch:str) -> EdgeTypeID|NodeTypeID:
    if ch in c.HETERO_NODE_TYPES:
        return c.HETERO_NODE_ID[ch]
    elif ch in c.HETERO_EDGE_TYPES:
        return c.HETERO_EDGE_ID[ch]
    else:
        raise ValueError(f"Unknown node or edge type: {ch}")

def ntID2str(id:int) -> str:
    if id in c.HETERO_NODE_ID.values():
        res = list(c.HETERO_NODE_ID.keys())[id]
        return res
    else:
        raise ValueError(f"Unknown node or edge type ID: {id}")

def etID2str(id:int):
    if id in c.HETERO_EDGE_ID.values():
        res = list(c.HETERO_EDGE_ID.keys())[id]
        return res
    else:
        raise ValueError(f"Unknown edge type ID: {id}")

def Add_In_Budget(budget:Budget, t:int, t_ntID:int, A:AdjacencyMatrix, NS:NeighborSet, n:int) -> None:
    # Added_node_t: Nodes in initial-output-set are initial-src-nodes.
    # t means the source-node in next iteration, but we treat it as the target-node in this iteration.
    for src_ntID in list(A.keys()):
        for etID in list(A[src_ntID].keys()):
            Dt = 1. / len(A[src_ntID][etID][t_ntID][t])
            for smpl_tgt_id in A[src_ntID][etID][t_ntID][t]:
                if smpl_tgt_id not in NS[src_ntID]:
                    budget[src_ntID][smpl_tgt_id] = Dt if not smpl_tgt_id in budget[src_ntID].keys() else budget[src_ntID][smpl_tgt_id] + Dt
    return

def HGTsampling(data:HeteroData, output_node_set:List[int], L:int, n:int, display:bool=False) -> None:

    # test
    output_node_set = output_node_set[:2]

    A:AdjacencyMatrix = defaultdict( # smpl_ntID 
        lambda: defaultdict( # etID
            lambda: defaultdict( # tgt_ntid
                lambda: defaultdict( # t_lnid
                    lambda: [] #s_lnids
                )
            )
        )
    )

    # Initialize adjacency-Matrix A
    for et, (tgt_nt, src_nt) in c.HETERO_EDGE_UNIT.items():
        tgt_lnIDs = [int(d) for d in data[tgt_nt, et, src_nt].edge_index[0].numpy()]
        src_lnIDs = [int(d) for d in data[tgt_nt, et, src_nt].edge_index[1].numpy()]
        for tgt_lnID, src_lnID in zip(tgt_lnIDs, src_lnIDs):
            A[str2id(src_nt)][str2id(et)][str2id(tgt_nt)][src_lnID].append(tgt_lnID) 
            # means number of neighbor nodes 
            # ex.) src_lnID has 3 tgt_lnIDs as neighbor nodes 
            # -> A[source_node_type][edge_type][target_node_type][source_lnID] = [tgt_lnID(1), tgt_lnID(2), tgt_lnID(3)]

    # check A construction
        
    OS:OutputSet = defaultdict( # outpusmpl_tid
        lambda: [] # output_code_ids
    )

    NS:NeighborSet = defaultdict( # sampled_node_type
        lambda: [] # sampled_code_ids
    )

    # Initialize the output node set OS with the provided output_node_set
    for init_lnID in output_node_set:
        OS[INIT_OS_KEY].append(init_lnID)

    NS = OS # Initialize sampled node set as output node set

    Prob = defaultdict( # sampled_node_type
        lambda: defaultdict( # sampled_code_id
            lambda: 0.0 #[sampling_probability]
        )
    )

    budget:Budget = defaultdict( # sampled_node_type
        lambda: defaultdict( # sampled_code_id
            lambda: 0.0 #[sampled_score]
        )
    )

    for tgt_ntID in list(NS.keys()): # init: src is NONE, tgt is INIT_OS_KEY
        for tgt_lnID in NS[tgt_ntID]:
            Add_In_Budget(budget, tgt_lnID, tgt_ntID, A, NS, n)
    
    for l in range(L):
        for smpl_src_ntID in list(budget.keys()):

            # Compute sampling probabilities for each node in Budget
            for src_lnID in budget[smpl_src_ntID]:
                Prob[smpl_src_ntID][src_lnID] = budget[smpl_src_ntID][src_lnID]**2

            # Normalize Probabilities
            prob_sum = sum(Prob[smpl_src_ntID].values())
            for src_lnID in Prob[smpl_src_ntID]:
                Prob[smpl_src_ntID][src_lnID] /= prob_sum

            # Sample n nodes from Budget using Prob
            sampled_ids = np.random.choice(
                list(Prob[smpl_src_ntID].keys()), 
                size=min(n, len(Prob[smpl_src_ntID])), 
                replace=False, 
                p=list(Prob[smpl_src_ntID].values())
            )

            samples_keys = list(budget[smpl_src_ntID].keys())

            # Create a new sampled node set NS for the current iteration
            NS = defaultdict( # src_tid
                lambda: [] # s_code_ids
            )

            for src_lnID in sampled_ids:
                NS[smpl_src_ntID].append(src_lnID)


            for smpl_src_lnID in samples_keys:

                # Add sampled node into OS
                OS[smpl_src_ntID].append(smpl_src_lnID)

                # Add neighbors of t to Budget
                Add_In_Budget(budget, smpl_src_lnID, smpl_src_ntID, A, NS, n)

                # Remove sampled node t from Budget
                budget[smpl_src_ntID].pop(smpl_src_lnID)

    # Reconstruct the sampled adjacnecy matrix ~A among the sampled nodes OS from A
    for et, (tgt_nt, src_nt) in c.HETERO_EDGE_UNIT.items():
        
        mask = np.all(
            np.vectorize(lambda lnID: lnID in OS[str2id(tgt_nt)])(data[tgt_nt, et, src_nt].edge_index.numpy()), 
            axis=0 # shape: [num_edges]
        )

        data[tgt_nt, et, src_nt].edge_index = torch.tensor(data[tgt_nt, et, src_nt].edge_index.numpy()[:, mask], dtype=torch.long).cpu()
        data[tgt_nt, et, src_nt].attr = torch.tensor(data[tgt_nt, et, src_nt].attr.numpy()[mask]).cpu()
        data[tgt_nt, et, src_nt].etIDs = torch.tensor(data[tgt_nt, et, src_nt].etIDs.numpy()[mask]).cpu()

    if display:
        print("sampling result")
        for ntID, smpl_lnIDs in OS.items(): 
            print(ntID, len(smpl_lnIDs))

    return