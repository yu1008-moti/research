from torch_geometric.data import HeteroData
from collections import defaultdict
from typing import List, Dict
import torch
import numpy as np

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
    if ch in c.HETERO_NODE_ID:
        return c.HETERO_NODE_ID[ch]
    elif ch in c.HETERO_EDGE_ID:
        return c.HETERO_EDGE_ID[ch]
    else:
        raise ValueError(f"Unknown node or edge type: {ch}")

def n_id2type(id:int) -> str:
    if id in c.HETERO_NODE_ID.values():
        return list(c.HETERO_NODE_ID.keys())[list(c.HETERO_NODE_ID.values()).index(id)]
    else:
        raise ValueError(f"Unknown node or edge type ID: {id}")

def e_id2type(id:int):
    if id in c.HETERO_EDGE_ID.values():
        return list(c.HETERO_EDGE_ID.keys())[list(c.HETERO_EDGE_ID.values()).index(id)]
    else:
        raise ValueError(f"Unknown edge type ID: {id}")

def Add_In_Budget(budget:Budget, smpl_tgt_cid:int, smpl_tgt_tid:int, A:AdjacencyMatrix, NS:NeighborSet, n:int) -> None:
    for src_tid in list(A.keys()):
        for edge_tid in list(A[src_tid].keys()):
            if smpl_tgt_cid not in A[src_tid][edge_tid][smpl_tgt_tid]:
                continue
            all_tgt_ids = A[src_tid][edge_tid][smpl_tgt_tid][smpl_tgt_cid]
            if len(all_tgt_ids) < n:
                smpl_tgt_ids = all_tgt_ids
            else:
                smpl_tgt_ids = np.random.choice(all_tgt_ids, n, replace = False)
            Dt = 1. / len(smpl_tgt_ids)
            for smpl_tgt_id in smpl_tgt_ids:
                if smpl_tgt_id not in NS[src_tid]:
                    budget[src_tid][smpl_tgt_id] += Dt
    return

def HGTsampling(data:HeteroData, output_node_set:List[int], L:int, n:int) -> OutputSet:

    A:AdjacencyMatrix = defaultdict( # smpl_tid 
        lambda: defaultdict( # edge_tid
            lambda: defaultdict( # src_tid
                lambda: defaultdict( # t_cid
                    lambda: [] #s_cids
                )
            )
        )
    )

    # Initialize adjacency-Matrix A
    for edge_tid, (tgt_tid, src_tid) in c.HETERO_EDGE_DICT.items():
        t_code_ids:torch.Tensor = data[tgt_tid, edge_tid, src_tid].codeIDs_i
        s_code_ids:torch.Tensor = data[tgt_tid, edge_tid, src_tid].codeIDs_j
        for t_cid, s_cid in zip(t_code_ids.tolist(), s_code_ids.tolist()):
            A[str2id(src_tid)][str2id(edge_tid)][str2id(tgt_tid)][t_cid].append(s_cid)
        
    OS:OutputSet = defaultdict( # outpusmpl_tid
        lambda: [] # output_code_ids
    )

    NS:NeighborSet = defaultdict( # sampled_node_type
        lambda: [] # sampled_code_ids
    )

    # Initialize the output node set OS with the provided output_node_set
    for init_cid in output_node_set:
        OS[INIT_OS_KEY].append(init_cid)

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

    for tgt_tids in list(NS.keys()):
        for tgt_cid in NS[tgt_tids]:
            Add_In_Budget(budget, tgt_cid, tgt_tids, A, NS, n)
    
    for l in range(L):
        for smpl_src_tid in list(budget.keys()):

            # Compute sampling probabilities for each node in Budget
            for s_cid in budget[smpl_src_tid]:
                Prob[smpl_src_tid][s_cid] = budget[smpl_src_tid][s_cid]**2

            # Normalize Probabilities
            prob_sum = sum(Prob[smpl_src_tid].values())
            for s_cid in Prob[smpl_src_tid]:
                Prob[smpl_src_tid][s_cid] /= prob_sum

            # Sample n nodes from Budget using Prob
            sampled_ids = np.random.choice(
                list(Prob[smpl_src_tid].keys()), 
                size=min(n, len(Prob[smpl_src_tid])), 
                replace=False, 
                p=list(Prob[smpl_src_tid].values())
            )

            samples_keys = np.array(list(budget[smpl_src_tid].keys()))

            # Create a new sampled node set NS for the current iteration
            NS = defaultdict( # src_tid
                lambda: [] # s_code_ids
            )

            for s_cid in sampled_ids:
                NS[smpl_src_tid].append(s_cid)


            for smpl_src_cid in samples_keys:

                # Add sampled node into OS
                OS[smpl_src_tid].append(smpl_src_cid)

                # Add neighbors of t to Budget
                Add_In_Budget(budget, smpl_src_cid, smpl_src_tid, A, NS, n)

                # Remove sampled node t from Budget
                budget[smpl_src_tid].pop(smpl_src_cid)

    # Reconstruct the sampled adjacnecy matrix ~A among the sampled nodes OS from A
    for edge_tid, (tgt_tid, src_tid) in c.HETERO_EDGE_DICT.items():        

        mask_i = data[tgt_tid, edge_tid, src_tid].node_type_i.apply_(lambda codeID: codeID in OS[str2id(tgt_tid)])
        mask_j = data[tgt_tid, edge_tid, src_tid].node_type_j.apply_(lambda codeID: codeID in OS[str2id(src_tid)])

        mask = mask_i & mask_j

        data[tgt_tid, edge_tid, src_tid].edge_index   = data[tgt_tid, edge_tid, src_tid].edge_index[:, mask]
        data[tgt_tid, edge_tid, src_tid].edge_attr    = data[tgt_tid, edge_tid, src_tid].edge_attr[mask]
        data[tgt_tid, edge_tid, src_tid].edge_type_id = data[tgt_tid, edge_tid, src_tid].edge_type_id[mask]
        data[tgt_tid, edge_tid, src_tid].node_type_i  = data[tgt_tid, edge_tid, src_tid].node_type_i[mask]
        data[tgt_tid, edge_tid, src_tid].node_type_j  = data[tgt_tid, edge_tid, src_tid].node_type_j[mask]
        data[tgt_tid, edge_tid, src_tid].codeIDs_i    = data[tgt_tid, edge_tid, src_tid].codeIDs_i[mask]
        data[tgt_tid, edge_tid, src_tid].codeIDs_j    = data[tgt_tid, edge_tid, src_tid].codeIDs_j[mask]

    return OS