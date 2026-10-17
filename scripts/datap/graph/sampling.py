from torch_geometric.data import HeteroData
from collections import defaultdict
from typing import List, Dict
import torch
import numpy as np

import scripts.datap.graph.const as c


HETERO_EDGE_DICT = c.HETERO_EDGE_DICT

T, S = 0, 1  # T: target node, S: source node

__all__ = ['HGTsampling']


def Add_In_Budget(Budget, t_node, A, NS) -> None:
    for s_node_type, ts_edge_type in A[t_node].items():
        Dt = 1/len(A[t_node]) # get normalized degree of added node t regarding to <τ, e, τ(t)>
        for s_code_id in A[t_node][s_node_type][ts_edge_type][S]:
            if s_code_id not in NS: 
                Budget[s_node_type][s_code_id][0] += Dt
            # This dataset can ignore time decay,
            # so it don't have "time" attribute 
    return

def HGTsampling(data:HeteroData, output_node_set:List[str], L:int, n:int) -> Dict[str, List[int]]:

    A = defaultdict( # t_node_type 
        lambda: defaultdict( # s_node_type
            lambda: defaultdict( # ts_edge_type
                lambda: [] # t_code_ids, s_code_ids
            )
        )
    )

    # Initialize adjacency-Matrix A
    for ts_edge_type, (t_node_type, s_node_type) in HETERO_EDGE_DICT.items():
        t_code_ids:torch.Tensor = data[t_node_type, ts_edge_type, s_node_type].node_type_i
        s_code_ids:torch.Tensor = data[t_node_type, ts_edge_type, s_node_type].node_type_j
        A[t_node_type][s_node_type][ts_edge_type] = [t_code_ids, s_code_ids]

    OS = defaultdict( # s_node_type
        lambda: [] # s_code_ids
    )

    for t_node_type in output_node_set:
        t_code_ids:torch.Tensor = data[t_node_type].codeIDs
        OS[t_node_type] = t_code_ids.tolist()

    NS = OS # Initialize sampled mpde set as output node set

    Prob = defaultdict( # s_node_type
        lambda: defaultdict( # s_code_id
            lambda: 0.0 #[sampling_probability]
        )
    )

    Budget = defaultdict( # s_node_type
        lambda: defaultdict( # s_code_id
            lambda: 0.0 #[sampled_score]
        )
    )

    for t_node in NS:
        Add_In_Budget(Budget, t_node, A, NS)
    
    for l in range(L):
        for s_node_type in Budget:

            # Compute sampling probabilities for each node in Budget
            for s_code_id in Budget[s_node_type]:
                Prob[s_node_type][s_code_id] = Budget[s_node_type][s_code_id]**2

            # Normalize Probabilities
            prob_sum = sum(Prob[s_node_type].values())
            for s_code_id in Prob[s_node_type]:
                Prob[s_node_type][s_code_id] /= prob_sum

            # Sample n nodes from Budget using Prob
            sampled_code_ids = np.random.choice(
                list(Prob[s_node_type].keys()), 
                size=min(n, len(Prob[s_node_type])), 
                replace=False, 
                p=list(Prob[s_node_type].values())
            )

            for s_code_id in sampled_code_ids:

                # Add sampled node into OS
                OS[s_node_type].append(s_code_id)

                # Add neighbors of t to Budget
                Add_In_Budget(Budget, t_node, A, NS)

                # Remove sampled node t from Budget
                Budget[s_node_type].pop(s_code_id)

    # Reconstruct the sampled adjacnecy matrix ~A among the sampled nodes OS from A
    for ts_edge_type, (t_node_type, s_node_type) in HETERO_EDGE_DICT.items():

        mask_i = data[t_node_type, ts_edge_type, s_node_type].node_type_i.apply_(lambda codeID: codeID in OS[t_node_type])
        mask_j = data[t_node_type, ts_edge_type, s_node_type].node_type_j.apply_(lambda codeID: codeID in OS[s_node_type])

        mask = mask_i & mask_j

        data[t_node_type, ts_edge_type, s_node_type].edge_index   = data[t_node_type, ts_edge_type, s_node_type].edge_index[:, mask]
        data[t_node_type, ts_edge_type, s_node_type].edge_attr    = data[t_node_type, ts_edge_type, s_node_type].edge_attr[mask]
        data[t_node_type, ts_edge_type, s_node_type].edge_type_id = data[t_node_type, ts_edge_type, s_node_type].edge_type[mask]
        data[t_node_type, ts_edge_type, s_node_type].node_type_i  = data[t_node_type, ts_edge_type, s_node_type].node_type_i[mask]
        data[t_node_type, ts_edge_type, s_node_type].node_type_j  = data[t_node_type, ts_edge_type, s_node_type].node_type_j[mask]
        data[t_node_type, ts_edge_type, s_node_type].codeIDs_i    = data[t_node_type, ts_edge_type, s_node_type].codeIDs_i[mask]
        data[t_node_type, ts_edge_type, s_node_type].codeIDs_j    = data[t_node_type, ts_edge_type, s_node_type].codeIDs_j[mask]

    return OS