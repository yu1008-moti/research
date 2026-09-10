from typing import Tuple
import pickle
from pathlib import Path
import os

from scripts.datap.graph_v2.tools.edge_matrix.spacial import SpacialEdgeMatrix as sem
from scripts.datap.graph_v2.tools.edge_matrix.temporal import TemporalEdgeMatrix as tem
from scripts.datap.graph_v2.tools.edge_matrix.constructor.spacial_c import Spacial
from scripts.datap.graph_v2.tools.edge_matrix.constructor.temporal_c import Temporal
from scripts.datap.graph_v2.tools.cons import train_constants as ct
from scripts.datap.graph_v2.tools.cons import print_constants as cp

def construct_graph(
        threshold: float,
        window_size_for_capm: int,
        window_size_for_corr: int,
        first_week_id: int,
        scratch: bool = False
    ) -> Tuple[sem, sem, tem, tem]:
    """グラフを構築する関数。既存のgraph.pklファイルが存在する場合はそれを読み込み、存在しない場合は新たに構築して保存する。
    Args:
        threshold (float): 相関係数の閾値
        window_size_for_capm (int): CAPM計算用のローリングウィンドウのサイズ
        window_size_for_corr (int): 相関計算用のローリングウィンドウのサイズ
        first_week_id (int): 最初の週ID
        scratch (bool, optional): 既存のgraph.pklファイルを削除して新たに構築するかどうか。デフォルトはFalse。
    Returns:
        Tuple[SpacialEdgeMatrix, SpacialEdgeMatrix, TemporalEdgeMatrix, TemporalEdgeMatrix]: 構築されたspacialおよびtemporalのエッジマトリックス
    """

    # scratch mode enabled
    if scratch:
        if Path(ct.GRAPH_STORED_PATH).exists() or Path(ct.RESIDUAL_STORED_PATH).exists() == False:
            print("You designated scratch mode, but files are not found.")
            print("Please check the following files:")
            print(f"\t1. {ct.GRAPH_STORED_PATH} : {'Found' if Path(ct.GRAPH_STORED_PATH).exists() else 'Not Found'}")
            print(f"\t2. {ct.RESIDUAL_STORED_PATH} : {'Found' if Path(ct.RESIDUAL_STORED_PATH).exists() else 'Not Found'}")
            print(f"[{cp.MAGENTA}scratch mode disabled{cp.RESET}]")
        else:
            print(f"[{cp.MAGENTA}scratch mode enabled{cp.RESET}]")
            sentense = f"Are You sure remove the existing below files? \n\t1. [{cp.CYAN}{ct.GRAPH_STORED_PATH}{cp.RESET}\n\t2. {cp.CYAN}{ct.RESIDUAL_STORED_PATH}{cp.RESET} \n(yes/no): "
            # 入力受付
            while True:
                user_input = input(sentense)
                if user_input.lower() == "yes":
                    if Path(ct.GRAPH_STORED_PATH).exists():
                        os.remove(ct.GRAPH_STORED_PATH)
                    if Path(ct.RESIDUAL_STORED_PATH).exists():
                        os.remove(ct.RESIDUAL_STORED_PATH)
                    print("Existing graph.pkl and returns_residual_matrix.parquet files removed.")
                    break
                elif user_input.lower() == "no":
                    print("Aborting graph construction.")
                    exit(0)
                else:
                    print("Invalid input. Please enter 'yes' or 'no'.")

    # graph.pkl file already exists
    # Use this file
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

    # graph.pkl file does not exist
    # construct the graph and save it to graph.pkl
    else:
        Spacial_emc = Spacial(
            threshold=threshold,
            window_size_for_capm=window_size_for_capm,
            window_size_for_corr=window_size_for_corr,
            first_week_id=first_week_id,
            )

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


