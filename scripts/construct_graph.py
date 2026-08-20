from typing import Tuple
import pickle
from pathlib import Path

from scripts.datap.graph.edge_matrix.spacial import SpacialEdgeMatrix as sem
from scripts.datap.graph.edge_matrix.temporal import TemporalEdgeMatrix as tem
from scripts.datap.graph.edge_matrix.constructor.spacial_c import Spacial
from scripts.datap.graph.edge_matrix.constructor.temporal_c import Temporal
from scripts.datap.graph.cons import train_constants as ct

def construct_graph() -> Tuple[sem, sem, tem, tem]:

    if Path(ct.GRAPH_STORED_PATH).exists():
        print("graph.pkl already exists, loading it...")
        with open(ct.GRAPH_STORED_PATH, "rb") as f:
            Sp_Mat_firm2firm, Sp_Mat_fin2firm, Tm_Mat_firm2firm, Tm_Mat_fin2fin = pickle.load(f)
            if     not isinstance(Sp_Mat_firm2firm, sem) \
                or not isinstance(Sp_Mat_fin2firm,  sem) \
                or not isinstance(Tm_Mat_firm2firm, tem) \
                or not isinstance(Tm_Mat_fin2fin,   tem):
                raise TypeError("Loaded objects are not of the expected types.")
        return Sp_Mat_firm2firm, Sp_Mat_fin2firm, Tm_Mat_firm2firm, Tm_Mat_fin2fin
    
    else:
        Spacial_emc = Spacial()

        print("using device:", Spacial_emc.device)

        Sp_Mat_firm2firm = Spacial_emc.register_firm2firm_edge()
        Sp_Mat_fin2firm = Spacial_emc.register_fin2firm_edge()

        Temporal_emc = Temporal(
            spacial_firm2firm_edge_list = Spacial_emc.spacial_firm2firm_edge_list,
            spacial_fin2firm_edge_list = Spacial_emc.spacial_fin2firm_edge_list,
            firm_id_order = Spacial_emc.firm_id_order,
            result_fetched_prices = Spacial_emc.result_fetched_prices,
            result_fetched_financials = Spacial_emc.result_fetched_financials
        )

        Tm_Mat_firm2firm = Temporal_emc.register_firm2firm_edge()
        Tm_Mat_fin2fin = Temporal_emc.register_fin2fin_edge()

        print("finished constructing spacial and temporal edge matrices")

        with open(ct.GRAPH_STORED_PATH, "wb") as f:
            pickle.dump((Sp_Mat_firm2firm, Sp_Mat_fin2firm, Tm_Mat_firm2firm, Tm_Mat_fin2fin), f)

        return Sp_Mat_firm2firm, Sp_Mat_fin2firm, Tm_Mat_firm2firm, Tm_Mat_fin2fin


