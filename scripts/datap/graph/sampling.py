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

def Add_In_Budget(budget:Budget, smpl_tgt_lnID:int, smpl_tgt_ntID:int, A:AdjacencyMatrix, NS:NeighborSet, n:int) -> None:
    for src_tid in list(A.keys()):
        for edge_tid in list(A[src_tid].keys()):
            if smpl_tgt_lnID not in A[src_tid][edge_tid][smpl_tgt_ntID]:
                continue
            all_tgt_ids = A[src_tid][edge_tid][smpl_tgt_ntID][smpl_tgt_lnID]
            if len(all_tgt_ids) < n:
                smpl_tgt_ids = all_tgt_ids
            else:
                smpl_tgt_ids = np.random.choice(all_tgt_ids, n, replace = False)
            Dt = 1. / len(smpl_tgt_ids)
            for smpl_tgt_id in smpl_tgt_ids:
                if smpl_tgt_id not in NS[src_tid]:
                    budget[src_tid][smpl_tgt_id] += Dt
    return

def HGTsampling(data:HeteroData, output_node_set:List[int], L:int, n:int, display:bool=False) -> None:

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
        tgt_lnIDs:torch.Tensor = data[tgt_nt, et, src_nt].edge_index[0]
        src_lnIDs:torch.Tensor = data[tgt_nt, et, src_nt].edge_index[1]
        for tgt_lnID, src_lnID in zip(tgt_lnIDs.tolist(), src_lnIDs.tolist()):
            A[str2id(src_nt)][str2id(et)][str2id(tgt_nt)][tgt_lnID].append(src_lnID)
        
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

    for tgt_ntID in list(NS.keys()):
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

            samples_keys = np.array(list(budget[smpl_src_ntID].keys()))

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

        mask_i = data[tgt_nt, et, src_nt].edge_index[0].apply_(lambda lnID: lnID in OS[str2id(tgt_nt)])
        mask_j = data[tgt_nt, et, src_nt].edge_index[1].apply_(lambda lnID: lnID in OS[str2id(src_nt)])

        mask = mask_i & mask_j

        data[tgt_nt, et, src_nt].edge_index   = data[tgt_nt, et, src_nt].edge_index[:, mask]
        data[tgt_nt, et, src_nt].attr    = data[tgt_nt, et, src_nt].attr[mask]
        data[tgt_nt, et, src_nt].etIDs = data[tgt_nt, et, src_nt].etIDs[mask]

    if display:
        print("sampling result")
        for ntID, smpl_lnIDs in OS.items(): 
            print(ntID, len(smpl_lnIDs))

    return