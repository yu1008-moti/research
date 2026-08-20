import torch
from typing import List, Tuple, Iterator
import pandas as pd
import numpy as np

from scripts.datap.graph.edge_matrix.element import NodeSet
from scripts.datap.graph.cons import train_constants as tc
from scripts.datap.graph.edge_matrix.temporal import TemporalEdgeMatrix as tem
from scripts.datap.graph.edge_matrix.constructor.utils import u_common


class _utils_firm2firm:
    """時間方向の企業 - 企業エッジを構築するためのヘルパー関数群
    """

    @staticmethod
    def _iter_temporal_firm2firm_matrix(
        firm_prices_exists_matrix: pd.DataFrame, 
        device: str, 
        firm_id_order: pd.Index
        ) -> Iterator[Tuple[float, int, int, torch.Tensor]]:
        """企業の価格データの存在有無を表す疎行列を構築するジェネレーター関数
        Args:
            firm_prices_exists_matrix (pd.DataFrame): 企業の価格データの存在有無を表すDataFrame
            device (str): 使用するデバイス（CPUまたはGPU）
            firm_id_order (pd.Index): 登録された企業コードのインデックス
        Yields:
            Iterator[Tuple[int, int, torch.Tensor]]: 前週ID、現在週ID、および対応する疎行列のタプルを返すジェネレーター
        """

        # create an initialized adjacent matrix with zeros
        initial_adjacent_matrix = torch.zeros(
            (len(firm_id_order), len(firm_id_order)), 
            dtype=torch.float32, 
            device=device
            )

        # get week_id list
        weekid_list:List[int] = firm_prices_exists_matrix.index.tolist()

        # get adjacent matrix for each week_id(t-1) and week_id(t)
        for week_id_key in range(1, len(weekid_list)):
            
            u_common.display_iter(
                Task_Summary="build temporal firm2firm graph weekly", 
                week_id=weekid_list[week_id_key]
            )
            previous_week_id = weekid_list[week_id_key - 1] # week_id(t-1)
            current_week_id = weekid_list[week_id_key] # week_id(t)

            # matrix(t-1) + matrix(t) > 0   => exists
            # matrix(t-1) + matrix(t) = NaN => not exists
            initial_adjacent_matrix[
                torch.arange(len(firm_id_order)), 
                torch.arange(len(firm_id_order))
            ] = (
                torch.tensor( # matrix that checks the existence of price data at week_id(t-1)
                firm_prices_exists_matrix[firm_prices_exists_matrix.index == previous_week_id].values, 
                dtype=torch.float32, 
                device=device
            ) + torch.tensor( # matrix that checks the existence of price data at week_id(t)
                firm_prices_exists_matrix[firm_prices_exists_matrix.index == current_week_id].values, 
                dtype=torch.float32, 
                device=device
            )).clamp(max=1).nan_to_num(nan=0.0)  # if exists, set to 1, else set to 0

            # return week_id(t-1), week_id(t), temporal_firm2firm_edge_matrix
            yield week_id_key/len(weekid_list), previous_week_id, current_week_id, initial_adjacent_matrix.to_sparse()
            
            # set 0 to diagonal elements
            # by this, matrix is reset to initial state
            # TODO: below process may be changed or added some process
            initial_adjacent_matrix.fill_diagonal_(0)


class _utils_fin2fin:
    """時間方向の企業 - 企業エッジを構築するためのヘルパー関数群
    """

    @staticmethod
    def _iter_temporal_fin2fin_matrix(
        fin_report_exists_matrix: pd.DataFrame, 
        device: str, 
        firm_id_order: pd.Index
        ) -> Iterator[Tuple[float, None, int, torch.Tensor]]:
        """財務資料の存在有無を表す疎行列を構築するジェネレーター関数
        
        Args:
            fin_report_exists_matrix (pd.DataFrame): 財務資料の存在有無を示すDataFrame
            device (str): 使用するデバイス
            firm_id_order (pd.Index): 企業IDの順序

        Yields:
            Tuple[None, int, torch.Tensor]: (前週ID, 現在週ID, 時間方向の企業間エッジ行列)
        """
        # create an initialized adjacent matrix with zeros
        initial_adjacent_matrix = torch.zeros((len(firm_id_order), len(firm_id_order)), dtype=torch.float32, device=device)

        # get week_id list
        weekid_list:List[int] = fin_report_exists_matrix.index.tolist()

        # originally, fin_report_exists_matrix has missing some tickers
        # add missing tickers
        exists_finsummary_df = pd.concat(
            [
                fin_report_exists_matrix, 
                pd.DataFrame(np.nan, index=fin_report_exists_matrix.index, columns=firm_id_order.difference(fin_report_exists_matrix.columns))
            ], axis=1
        ).replace( # replace '1Q', '2Q', '3Q', 'FY' with only 1
            r'.*', 1, regex=True
        )

        # change the order of columns to firm_id_order
        # this order is common for all edge matrices
        exists_finsummary_df.columns = firm_id_order

        # all 1 convert to correspoding week_id 
        exists_finsummary_df = pd.DataFrame(
            exists_finsummary_df.index.values.reshape(-1, 1) * exists_finsummary_df.values,
            index=exists_finsummary_df.index,
            columns=exists_finsummary_df.columns
        )

        # set current week_id value to previous week_id
        # this make edge between week_id(t-k) and week_id(t)
        # if fin report exists at week_id(t), matrix records week_id(t-k), not 1
        exists_finsummary_df = (
            exists_finsummary_df.ffill().shift() * exists_finsummary_df.clip(upper=1)
        ).fillna(0)


        # replace diagonal elements 0 to week_id(t-k)
        for i, current_week_id in enumerate(weekid_list, start=1):
            u_common.display_iter(
                Task_Summary="build temporal fin2fin graph weekly",
                week_id=current_week_id,
                procssing_ratio=i/len(weekid_list)
            )
            initial_adjacent_matrix[
                torch.arange(len(firm_id_order)),
                torch.arange(len(firm_id_order))
            ] = torch.tensor(
                exists_finsummary_df[exists_finsummary_df.index == current_week_id].astype(int).values, 
                dtype=torch.float32, 
                device=device
            )
            yield i/len(weekid_list), None, current_week_id, initial_adjacent_matrix.to_sparse()
            # return

            # set 0 to diagonal elements
            # by this, matrix is reset to initial state
            # TODO: below process may be changed or added some process
            initial_adjacent_matrix.fill_diagonal_(0)


class Temporal:
    """時間方向のエッジ行列を構築するためのクラス
    空間方向のエッジ行列を入力として、時間方向のエッジ行列を構築する
    """

    def __init__(
            self, 
            spacial_firm2firm_edge_list: list[Tuple[int, torch.Tensor]], 
            spacial_fin2firm_edge_list: list[Tuple[int, torch.Tensor]],
            firm_id_order: pd.Index,
            result_fetched_prices: pd.DataFrame,
            result_fetched_financials: pd.DataFrame,
            ):

        # Initialize by arguments
        self.spacial_firm2firm_edge_list : list[Tuple[int, torch.Tensor]] = spacial_firm2firm_edge_list
        self.spacial_fin2firm_edge_list : list[Tuple[int, torch.Tensor]] = spacial_fin2firm_edge_list
        self.result_fetched_prices : pd.DataFrame = result_fetched_prices
        self.result_fetched_financials : pd.DataFrame = result_fetched_financials
        self.firm_id_order : pd.Index = firm_id_order

        # Expected Return Variables
        self.temporal_firm2firm_edge_list : list[Tuple[int, int, torch.Tensor]] = []
        self.temporal_fin2firm_edge_list : list[Tuple[int, int, torch.Tensor]] = []
        self.temporal_fin2fin_edge_list : list[Tuple[int, int, torch.Tensor]] = []
        self.first_week_id : int = tc.FIRST_WEEK_ID


    def register_firm2firm_edge(self) -> tem:
        firm_prices_exists_matrix = self.result_fetched_prices.pivot(index="week_id", columns="Code", values="AdjO")[self.firm_id_order]
        Node_ax1 = NodeSet(self.firm_id_order, "Firm")
        Node_ax2 = NodeSet(self.firm_id_order, "Firm")
        for procssing_ratio, previous_week_id, current_week_id, sparse_firm2firm_edge_matrix in _utils_firm2firm._iter_temporal_firm2firm_matrix(
            firm_prices_exists_matrix, 
            device=tc.DEVICE, 
            firm_id_order=self.firm_id_order
            ):
            if current_week_id < self.first_week_id:
                continue

            # display progress
            u_common.display_iter(
                Task_Summary="build temporal firm2firm graph weekly", 
                week_id=current_week_id, 
                procssing_ratio=procssing_ratio,
                sparse_Node2Node_edge_matrix=sparse_firm2firm_edge_matrix
            )

            self.temporal_firm2firm_edge_list.append((previous_week_id, current_week_id, sparse_firm2firm_edge_matrix))  # 疎行列のみ保持
        return tem(self.temporal_firm2firm_edge_list, Node_ax1, Node_ax2)

    
    def register_fin2firm_edge(self) -> None: # -> TemporalEdgeMatrix:
        pass


    def register_fin2fin_edge(self) -> tem:
        fin_report_exists_matrix = self.result_fetched_financials.pivot(index="week_id", columns="Code", values="CurPerType")
        Node_ax1 = NodeSet(self.firm_id_order, "Fin")
        Node_ax2 = NodeSet(self.firm_id_order, "Fin")
        for procssing_ratio, _, current_week_id, sparse_fin2fin_edge_matrix in _utils_fin2fin._iter_temporal_fin2fin_matrix(
            fin_report_exists_matrix, 
            device=tc.DEVICE, 
            firm_id_order=self.firm_id_order
        ):
            if current_week_id < self.first_week_id:
                continue

            # display progress
            u_common.display_iter(
                Task_Summary="build temporal fin2fin graph weekly", 
                week_id=current_week_id, 
                procssing_ratio=procssing_ratio,
                sparse_Node2Node_edge_matrix=sparse_fin2fin_edge_matrix
            )

            self.temporal_fin2fin_edge_list.append((0, current_week_id, sparse_fin2fin_edge_matrix))  # 疎行列のみ保持
        return tem(self.temporal_fin2fin_edge_list, Node_ax1, Node_ax2)

