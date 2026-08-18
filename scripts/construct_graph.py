from data_processing.graph import EdgeMatrixConstructor as emc
from typing import Tuple
from data_processing.graph import SpacialEdgeMatrix, TemporalEdgeMatrix

def construct_graph() -> Tuple[SpacialEdgeMatrix, SpacialEdgeMatrix, TemporalEdgeMatrix, TemporalEdgeMatrix]:
    Spacial_emc = emc.Spacial()

    print("using device:", Spacial_emc.device)

    Sp_Mat_firm2firm = Spacial_emc.register_firm2firm_edge()
    Sp_Mat_fin2firm = Spacial_emc.register_fin2firm_edge()

    Temporal_emc = emc.Temporal(
        spacial_firm2firm_edge_list = Spacial_emc.spacial_firm2firm_edge_list,
        spacial_fin2firm_edge_list = Spacial_emc.spacial_fin2firm_edge_list,
        firm_id_order = Spacial_emc.firm_id_order,
        result_fetched_prices = Spacial_emc.result_fetched_prices,
        result_fetched_financials = Spacial_emc.result_fetched_financials
    )

    Tm_Mat_firm2firm = Temporal_emc.register_firm2firm_edge()
    Tm_Mat_fin2fin = Temporal_emc.register_fin2fin_edge()

    print("finished constructing spacial and temporal edge matrices")

    return Sp_Mat_firm2firm, Sp_Mat_fin2firm, Tm_Mat_firm2firm, Tm_Mat_fin2fin