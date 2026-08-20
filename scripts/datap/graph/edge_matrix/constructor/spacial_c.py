import torch
from typing import List, Tuple, Iterator
import pandas as pd
import numpy as np
from pathlib import Path
from statsmodels.regression.rolling import RollingOLS
import statsmodels.api as sm


from scripts.datap.graph.cons import train_constants as tc
from scripts.datap.graph.sql import fetch
from scripts.datap.graph.edge_matrix.element import NodeSet
from scripts.datap.graph.edge_matrix.spacial import SpacialEdgeMatrix as sem
from scripts.datap.graph.edge_matrix.constructor.utils import u_common

class Spacial:


    class _utils_firm2firm:
        """空間方向にの企業 - 企業エッジを構築するためのヘルパー関数群
        """

        @staticmethod
        def _rolling_capm_residual(
            stock_ret: pd.Series, 
            market_ret: pd.Series, 
            window: int = 52
        ) -> Tuple[pd.Series, pd.Series]:
            """計算に用いる窓を指定し、計算範囲をずらしながらCAPMモデルの残差を計算する関数
            Args:
                stock_ret (pd.Series): 個別株のリターン系列
                market_ret (pd.Series): 市場全体のリターン系列
                window (int, optional): ローリングウィンドウのサイズ. Defaults to 52.
            """
            df = pd.concat([stock_ret, market_ret], axis=1, keys=["r_i", "r_m"]).dropna()
            X = sm.add_constant(df["r_m"])
            
            rols = RollingOLS(endog=df["r_i"], exog=X, window=window)
            rres = rols.fit()
            
            fitted = (rres.params["const"] + rres.params["r_m"] * df["r_m"])
            residual = df["r_i"] - fitted
            return residual, rres.params["r_m"]

        
        @staticmethod
        def _add_capm_factors_column(
            fetched_prices: pd.DataFrame, 
            window_size: int
        ) -> pd.DataFrame:
            """CAPMモデルの残差とベータを計算し、元の価格データに追加する関数
            Args:
                fetched_prices (pd.DataFrame): 価格データを含むDataFrame
                window_size (int): ローリングウィンドウのサイズ
            Returns:
                pd.DataFrame: CAPMモデルの残差とベータを追加したDataFrame
            """
            codes_length = len(fetched_prices["Code"].unique())
            unmatched_codes: List[Tuple[str, int]] = []
            fetched_prices["residual"] = np.nan
            fetched_prices["beta"] = np.nan

            if Path(tc.RESIDUAL_STORED_PATH).exists():

                u_common.display_note(
                    note_title="Returns Residual Matrix already exists",
                    content="Skip the calculation of CAPM Factors by rolling regression"
                )

                return pd.read_parquet(tc.RESIDUAL_STORED_PATH)

            for i, code in enumerate(fetched_prices["Code"].unique()):

                # display progress
                u_common.display_iter(
                    Task_Summary = "calculate CAPM Factors by rolling regression",
                    procssing_ratio = (i+1)/codes_length
                )

                # get the filtered result for the current code
                filtered_result: pd.DataFrame = fetched_prices[fetched_prices["Code"] == code]

                # filter the codes don't have enough data for rolling regression
                if len(filtered_result) < window_size:
                    unmatched_codes.append((code, len(filtered_result)))
                    continue

                # filter the result dataframe for the current code
                filtered_result: pd.DataFrame = fetched_prices[fetched_prices["Code"] == code]
                stock_returns = filtered_result["r_i"] - filtered_result["r_f"]
                market_returns = filtered_result["r_m"] - filtered_result["r_f"]
                residuals, betas = Spacial._utils_firm2firm._rolling_capm_residual(stock_returns, market_returns, window=window_size)
                fetched_prices.loc[filtered_result.index, "residual"] = residuals
                fetched_prices.loc[filtered_result.index, "beta"] = betas

            fetched_prices = fetched_prices[~fetched_prices["residual"].isna() & ~fetched_prices["beta"].isna()]

            u_common.display_note(
                note_title="Numbers of Codes have Unmatched length of Array",
                content=len(unmatched_codes)/codes_length
            )

            u_common.display_note(
                note_title="Numbers of Available Codes",
                content=(codes_length - len(unmatched_codes))/codes_length
            )

            returns_residual_matrix = fetched_prices.pivot(index="week_id", columns="Code", values="residual")

            returns_residual_matrix.to_parquet(
                tc.RESIDUAL_STORED_PATH, 
                engine="pyarrow"
            )

            return returns_residual_matrix


        @staticmethod
        def _iter_prices_adjacent_matrix(
            returns_residual_matrix: pd.DataFrame, 
            window_size: int, 
            device: str
        ) -> Iterator[Tuple[float, int, torch.Tensor]]:

            returns_residual = torch.tensor(returns_residual_matrix.values, dtype=torch.float32, device=device)
            returns_week_id:List[int] = returns_residual_matrix.index.values.tolist()

            T, N = returns_residual.shape

            # 初期ウィンドウの統計量
            buf = returns_residual[:window_size]  # (window, N)
            s1 = torch.sum(buf, dim=0) # (N,)  和
            G = buf.T @ buf # (N,N) 二乗和行列（Gram行列）

            for t in range(window_size, T):
                # --- ウィンドウ確定時点での統計量算出 ---
                mean = s1 / window_size
                cov = G / window_size - torch.outer(mean, mean)
                std = torch.sqrt(torch.diag(cov))
                corr = (cov / torch.outer(std, std))
                corr = torch.nan_to_num(corr, nan=0.0)  # NaNを0に置換
                corr.fill_diagonal_(0)  # 自己相関を除外
                mask = torch.abs(corr) > tc.THRESHOLD  # 閾値処理

                

                yield (t+1)/T, returns_week_id[t], (corr * mask).to_sparse() # ここでthreshold処理・エッジ抽出して即座に破棄する

                # --- スラ(イド：新しい週を追加、最も古い週を除去 ---
                x_new = returns_residual[t]
                x_old = returns_residual[t - window_size]
                s1 += x_new - x_old
                G += torch.outer(x_new, x_new) - torch.outer(x_old, x_old)


    class _utils_firm2fin:
        """空間方向にの企業 - 財務資料エッジを構築するためのヘルパー関数群
        """

        @staticmethod
        def _construct_fin_graph(
            exists_finsummary_df: pd.DataFrame, 
            weekid_list: List[int], 
            device: str, 
            registerd_codes: pd.Index
            ) -> Iterator[Tuple[float, int, torch.Tensor]]:
            """財務資料の存在有無を表す疎行列を構築するジェネレーター関数
            Args:
                exists_finsummary_df (pd.DataFrame): 財務資料の存在有無を表すDataFrame
                weekid_list (List[int]): 週IDのリスト
                device (str): 使用するデバイス（CPUまたはGPU）
                registerd_codes (pd.Index): 登録された企業コードのインデックス
            Returns:
                Iterator[Tuple[int, torch.Tensor]]: 週IDと対応する疎行列のタプルを返すジェネレーター
            """

            initial_adjacent_matrix = torch.zeros(
                (len(registerd_codes), len(registerd_codes)), 
                dtype=torch.float32, 
                device=device
            )

            for t, week_id in enumerate(weekid_list, start=1):
                initial_adjacent_matrix[
                    torch.arange(len(registerd_codes)), 
                    torch.arange(len(registerd_codes))
                ] = torch.tensor(
                    exists_finsummary_df[exists_finsummary_df.index == week_id].values, 
                    dtype=torch.float32, 
                    device=device
                )
                yield t/len(weekid_list), week_id, initial_adjacent_matrix.to_sparse()

                initial_adjacent_matrix.fill_diagonal_(0)


        @staticmethod
        def _get_financials_exists_matrix(
            financials_pivoted: pd.DataFrame, 
            registerd_codes: pd.Index
            ) -> pd.DataFrame:
            """財務資料の存在有無を表すDataFrameを構築する関数
            Args:
                financials_pivoted (pd.DataFrame): 財務資料のピボットされたDataFrame
                registerd_codes (pd.Index): 登録された企業コードのインデックス
            Returns:
                pd.DataFrame: 財務資料の存在有無を表すDataFrame
            """
            diff_ele = registerd_codes.difference(financials_pivoted.columns)
            weekid_ele = financials_pivoted.index

            additional_financials_data = pd.DataFrame(np.nan, index=weekid_ele, columns=diff_ele)

            exists_finsummary_df = \
            pd.concat(
                [financials_pivoted, additional_financials_data], axis=1
            ).replace(
                ['1Q', '2Q', '3Q', 'FY'], [1, 2, 3, 4]
            ).fillna(
                value = 0
            ).astype(
                int
            ).sort_index(axis=1)

            return exists_finsummary_df

    #-----------------------------------#
    #    BELOW IS THE MAIN FUNCTIONS    #
    #-----------------------------------#

    def __init__(self):
        self.firm_id_order : pd.Index
        self.spacial_firm2firm_edge_list : list[Tuple[int, torch.Tensor]] = []
        self.spacial_fin2firm_edge_list : list[Tuple[int, torch.Tensor]] = []
        self.window_size : int = tc.WINDOW_SIZE
        self.residuals_threshold : float = tc.THRESHOLD
        self.device : str = tc.DEVICE
        self.first_week_id : int = tc.FIRST_WEEK_ID
        self.result_fetched_prices : pd.DataFrame
        self.result_fetched_financials : pd.DataFrame


    def register_firm2firm_edge(self) -> sem:

        # fetch prices data
        self.result_fetched_prices = fetch.prices()

        # matrix representation of firm prices data is existing or not
        # with CAPM factors column added
        returns_residual_matrix = Spacial._utils_firm2firm._add_capm_factors_column(
            self.result_fetched_prices, 
            window_size=self.window_size
        )

        # to calc residuals, some tickers may have only NaN
        # so, need to set firm_id_order after calc them
        self.firm_id_order = returns_residual_matrix.columns

        Node_ax1 = NodeSet(self.firm_id_order, "Firm") # Firm Nodes
        Node_ax2 = NodeSet(self.firm_id_order, "Firm") # Firm Nodes

        # sparse_firm2firm_edge_matrix: sparsed edge matrix based torch.Tensor
        for procssing_ratio, week_id, sparse_firm2firm_edge_matrix in Spacial._utils_firm2firm._iter_prices_adjacent_matrix(
            returns_residual_matrix, 
            self.window_size, 
            self.device
        ):
            if week_id < self.first_week_id:
                continue

            # display progress
            u_common.display_iter(
                Task_Summary="build spacial firm2firm graph weekly", 
                week_id=week_id, 
                procssing_ratio=procssing_ratio,
                sparse_Node2Node_edge_matrix=sparse_firm2firm_edge_matrix
            )

            # append the matrix representation of the edge(firm - firm) to the list
            self.spacial_firm2firm_edge_list.append((week_id, sparse_firm2firm_edge_matrix))  # 疎行列のみ保持
        return sem(self.spacial_firm2firm_edge_list, Node_ax1, Node_ax2)


    def register_fin2firm_edge(self) -> sem:

        # fetch financials data
        # filter Tickers by registered firm_id_order
        self.result_fetched_financials = fetch.financials(self.firm_id_order.tolist())

        # matrix representation of financials data is existing or not
        financials_exists_matrix = Spacial._utils_firm2fin._get_financials_exists_matrix(
            self.result_fetched_financials.pivot(index="week_id", columns="Code", values="CurPerType"), 
            self.firm_id_order
        )

        # get the list of week_ids
        weekid_list = financials_exists_matrix.index.tolist()

        Node_Ax1 = NodeSet(self.firm_id_order, "Fin")  # Financial Nodes
        Node_Ax2 = NodeSet(self.firm_id_order, "Firm") # Firm Nodes

        # sparse_fin2firm_edge_matrix: sparsed edge matrix based torch.Tensor
        for procssing_ratio, week_id, sparse_fin2firm_edge_matrix in Spacial._utils_firm2fin._construct_fin_graph(
            financials_exists_matrix, 
            weekid_list, 
            device=self.device, 
            registerd_codes=self.firm_id_order
        ):

            # filter week_id by user-defined first_week_id
            if week_id < self.first_week_id:
                continue

            # display progress
            u_common.display_iter(
                Task_Summary="build spacial fin2firm graph weekly", 
                week_id=week_id, 
                procssing_ratio=procssing_ratio,
                sparse_Node2Node_edge_matrix=sparse_fin2firm_edge_matrix
            )

            # append the matrix representation of the edge(fin - firm) to the list
            self.spacial_fin2firm_edge_list.append((week_id, sparse_fin2firm_edge_matrix))  # 疎行列のみ保持
        
        return sem(self.spacial_fin2firm_edge_list, Node_Ax1, Node_Ax2)
