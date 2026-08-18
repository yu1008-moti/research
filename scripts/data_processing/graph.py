import numpy as np
import pandas as pd
import duckdb as db
import networkx as nx
import statsmodels.api as sm
from string import Template
from typing import List, Tuple, Dict, Any, Iterator, Optional
from statsmodels.regression.rolling import RollingOLS
import torch
from pathlib import Path

class Constants:
    # FETCH DATA CONSTANTS
    PATH_DB = "./db/synthesis/synthesis.duckdb"
    PATH_SQL_TO_FETCH_PRICES = "./graph_lab/sql/get_table_to_CAPM.sql"
    PATH_SQL_TO_FETCH_FINANCIALS = "./graph_lab/sql/get_fin_data_by_week.sql"
    YEAR_START = 2011
    YEAR_END = 2025

    # BUILD TRAIN DATASET CONSTANTS
    TRAIN_START_YEAR = 2015
    ROLLING_WINDOW = 52
    WINDOW_SIZE = 52
    THRESHOLD = 0.7
    FIRST_WEEK_ID = 201501
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

    # COLOR FOR PRINT FUNCTION
    CLEAR = '\033[2K'
    MAGENTA = '\033[35m'
    RESET = '\033[0m'

class SQLQuery:

    @staticmethod
    def _fetch(QUERY:str) -> pd.DataFrame:
        conn = db.connect(Constants.PATH_DB)
        result = conn.execute(QUERY).df()
        conn.close()
        return result

    # SQL QUERY TO FETCH DATA OF PRICES
    @staticmethod
    def fetch_prices() -> pd.DataFrame:
        with open(Constants.PATH_SQL_TO_FETCH_PRICES, "r") as f:
            EQUITY_FETCH_QUERY = Template(f.read()).substitute(
                    YEAR_START=Constants.YEAR_START*100, 
                    YEAR_END=(Constants.YEAR_END+1)*100
                )
        return SQLQuery._fetch(EQUITY_FETCH_QUERY)

    # SQL QUERY TO FETCH FINANCIAL DATA
    @staticmethod
    def fetch_financials(registered_nodes: list) -> pd.DataFrame:
        with open(Constants.PATH_SQL_TO_FETCH_FINANCIALS, "r") as f:
            FINANCIAL_STATEMENTS_FETCH_QUERY = Template(f.read()).substitute(
                    REGISTERED_CODES=registered_nodes
                )
        return SQLQuery._fetch(FINANCIAL_STATEMENTS_FETCH_QUERY)


class NodeSet:
    """ノードの集合を表すクラス
    縦軸と横軸のノードの順序とタイプを保持し、エイリアスを付与する機能を提供する
    """
    
    def __init__(self, node_order:pd.Index, node_type: str):
        """ノードの順序とタイプを初期化するコンストラクタ
        Args:
            node_order (pd.Index): ノードの順序を表すpandas Index
            node_type (str): ノードのタイプを表す文字列
        """
        self.node_order : pd.Index = node_order
        self.node_type : str = node_type


    def rename_nodes_with_alias(self) -> None:
        """ノードにエイリアスを付与するメソッド
        ノードの順序に基づいて、各ノードにエイリアスを付与し、ノードの順序を更新する
        """
        self.node_order = self.node_order + f"_{self.node_type}"


class TemporalEdgeMatrix:
    """時間方向のエッジ行列を表すクラス
    時間方向のエッジ行列を保持し、縦軸と横軸のノードセットを管理する
    """

    def __init__(
            self, 
            temporal_previous2current_edge_list: list[Tuple[int, int, torch.Tensor]], 
            node1: NodeSet, 
            node2: NodeSet
            ):
        """TemporalEdgeMatrixのコンストラクタ
        Args:
            temporal_previous2current_edge_list (list[Tuple[int, int, torch.Tensor]]): 時間方向のエッジ行列のリスト
            node1 (NodeSet): 縦軸のノードセット
            node2 (NodeSet): 横軸のノードセット
        """
        self.temporal_previous2current_edge_list : list[Tuple[int, int, torch.Tensor]] = temporal_previous2current_edge_list
        node1.rename_nodes_with_alias()
        node2.rename_nodes_with_alias()
        self.node1 : NodeSet = node1
        self.node2 : NodeSet = node2


class SpacialEdgeMatrix:
    """空間方向のエッジ行列を表すクラス
    空間方向のエッジ行列を保持し、縦軸と横軸のノードセットを管理する
    """

    def __init__(
            self, 
            spacial_node2node_edge_list: list[Tuple[int, torch.Tensor]], 
            node1: NodeSet, 
            node2: NodeSet
            ):
        """SpacialEdgeMatrixのコンストラクタ
        Args:
            spacial_node2node_edge_list (list[Tuple[int, torch.Tensor]]): 空間方向のエッジ行列のリスト
            node1 (NodeSet): 縦軸のノードセット
            node2 (NodeSet): 横軸のノードセット
        """
        self.spacial_node2node_edge_list : list[Tuple[int, torch.Tensor]] = spacial_node2node_edge_list
        node1.rename_nodes_with_alias()
        node2.rename_nodes_with_alias()
        self.node1 : NodeSet = node1
        self.node2 : NodeSet = node2


class EdgeMatrixConstructor:
    """エッジ行列を構築するためのクラス
    空間方向および時間方向のエッジ行列を構築する"""


    class _utils_common:
        """firm - firm, firm - finのエッジを構築するための共通ヘルパー関数群
        """

        @staticmethod
        def display_iter(
            Task_Summary:str, 
            week_id: Optional[int] = None, 
            procssing_ratio: Optional[float] = None,
            sparse_Node2Node_edge_matrix: Optional[torch.Tensor] = None
            ) -> None:
            """進捗状況を表示する関数
            この関数は、処理中のタスクの概要、週ID、処理の進捗率、および疎行列の形状を表示します。
            ただし、Task_Summaryは必須で、それ以外の引数は任意です。
            Args:
                Task_Summary (str): タスクの概要を示す文字列
                week_id (Optional[int], optional): 現在処理中の週ID. Defaults to None.
                procssing_ratio (Optional[float], optional): 処理の進捗率. Defaults to None.
                sparse_Node2Node_edge_matrix (Optional[torch.Tensor], optional): 現在処理中の疎行列. Defaults to None.
            """
            sentence_stack:List[str] = []

            if procssing_ratio is None:
                sentence_stack.insert(0, f'\r{Constants.CLEAR}')
                end = " "
            elif procssing_ratio < 1.0:
                sentence_stack.insert(0, f'\r{Constants.CLEAR}')
                end = " "
            else:
                end = "\n"

            sentence_stack.append(f"Processing [{Constants.MAGENTA}{Task_Summary}{Constants.RESET}] ")
            
            if week_id is not None:
                sentence_stack.append(f"Week ID: {week_id}")

            if sparse_Node2Node_edge_matrix is not None:
                sentence_stack.append(f"Firm - Firm Graph Shape: {sparse_Node2Node_edge_matrix.shape}")
                sentence_stack.append(f"Non-zero elements: {str(sparse_Node2Node_edge_matrix._nnz()).rjust(4)}")

            if procssing_ratio is not None:
                rounded_procssing_ratio = str(round(procssing_ratio*100, 2)).rjust(6)
                sentence_stack.append(f"Processing Ratio: {rounded_procssing_ratio}%")

            print(
                *sentence_stack,
                end=end
            )


        @staticmethod
        def display_note(note_title:str, content:Any):
            print(
                ' -',
                f"Title: [{Constants.MAGENTA}{note_title}{Constants.RESET}]: ",
                f"{content}"
            )


    class Temporal:
        """時間方向のエッジ行列を構築するためのクラス
        空間方向のエッジ行列を入力として、時間方向のエッジ行列を構築する
        """

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
                    
                    EdgeMatrixConstructor._utils_common.display_iter(
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
                    EdgeMatrixConstructor._utils_common.display_iter(
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


        #-----------------------------------#
        #    BELOW IS THE MAIN FUNCTIONS    #
        #-----------------------------------#


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
            self.first_week_id : int = Constants.FIRST_WEEK_ID


        def register_firm2firm_edge(self) -> TemporalEdgeMatrix:
            firm_prices_exists_matrix = self.result_fetched_prices.pivot(index="week_id", columns="Code", values="AdjO")[self.firm_id_order]
            Node_ax1 = NodeSet(self.firm_id_order, "Firm")
            Node_ax2 = NodeSet(self.firm_id_order, "Firm")
            for procssing_ratio, previous_week_id, current_week_id, sparse_firm2firm_edge_matrix in EdgeMatrixConstructor.Temporal._utils_firm2firm._iter_temporal_firm2firm_matrix(
                firm_prices_exists_matrix, 
                device=Constants.DEVICE, 
                firm_id_order=self.firm_id_order
                ):
                if current_week_id < self.first_week_id:
                    continue

                # display progress
                EdgeMatrixConstructor._utils_common.display_iter(
                    Task_Summary="build temporal firm2firm graph weekly", 
                    week_id=current_week_id, 
                    procssing_ratio=procssing_ratio,
                    sparse_Node2Node_edge_matrix=sparse_firm2firm_edge_matrix
                )

                self.temporal_firm2firm_edge_list.append((previous_week_id, current_week_id, sparse_firm2firm_edge_matrix))  # 疎行列のみ保持
            return TemporalEdgeMatrix(self.temporal_firm2firm_edge_list, Node_ax1, Node_ax2)

        
        def register_fin2firm_edge(self) -> None: # -> TemporalEdgeMatrix:
            pass


        def register_fin2fin_edge(self) -> TemporalEdgeMatrix:
            fin_report_exists_matrix = self.result_fetched_financials.pivot(index="week_id", columns="Code", values="CurPerType")
            Node_ax1 = NodeSet(self.firm_id_order, "Fin")
            Node_ax2 = NodeSet(self.firm_id_order, "Fin")
            for procssing_ratio, _, current_week_id, sparse_fin2fin_edge_matrix in EdgeMatrixConstructor.Temporal._utils_fin2fin._iter_temporal_fin2fin_matrix(
                fin_report_exists_matrix, 
                device=Constants.DEVICE, 
                firm_id_order=self.firm_id_order
            ):
                if current_week_id < self.first_week_id:
                    continue

                # display progress
                EdgeMatrixConstructor._utils_common.display_iter(
                    Task_Summary="build temporal fin2fin graph weekly", 
                    week_id=current_week_id, 
                    procssing_ratio=procssing_ratio,
                    sparse_Node2Node_edge_matrix=sparse_fin2fin_edge_matrix
                )

                self.temporal_fin2fin_edge_list.append((0, current_week_id, sparse_fin2fin_edge_matrix))  # 疎行列のみ保持
            return TemporalEdgeMatrix(self.temporal_fin2fin_edge_list, Node_ax1, Node_ax2)


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

                if Path("./scripts/data_processing/store/returns_residual_matrix.parquet").exists():

                    EdgeMatrixConstructor._utils_common.display_note(
                        note_title="Returns Residual Matrix already exists",
                        content="Skip the calculation of CAPM Factors by rolling regression"
                    )

                    return pd.read_parquet("./scripts/data_processing/store/returns_residual_matrix.parquet")

                for i, code in enumerate(fetched_prices["Code"].unique()):

                    # display progress
                    EdgeMatrixConstructor._utils_common.display_iter(
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
                    residuals, betas = EdgeMatrixConstructor.Spacial._utils_firm2firm._rolling_capm_residual(stock_returns, market_returns, window=window_size)
                    fetched_prices.loc[filtered_result.index, "residual"] = residuals
                    fetched_prices.loc[filtered_result.index, "beta"] = betas

                fetched_prices = fetched_prices[~fetched_prices["residual"].isna() & ~fetched_prices["beta"].isna()]

                EdgeMatrixConstructor._utils_common.display_note(
                    note_title="Numbers of Codes have Unmatched length of Array",
                    content=len(unmatched_codes)/codes_length
                )

                EdgeMatrixConstructor._utils_common.display_note(
                    note_title="Numbers of Available Codes",
                    content=(codes_length - len(unmatched_codes))/codes_length
                )

                returns_residual_matrix = fetched_prices.pivot(index="week_id", columns="Code", values="residual")

                returns_residual_matrix.to_parquet(
                    "./scripts/data_processing/store/returns_residual_matrix.parquet", 
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
                    mask = torch.abs(corr) > Constants.THRESHOLD  # 閾値処理

                    

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
            self.window_size : int = Constants.WINDOW_SIZE
            self.residuals_threshold : float = Constants.THRESHOLD
            self.device : str = Constants.DEVICE
            self.first_week_id : int = Constants.FIRST_WEEK_ID
            self.result_fetched_prices : pd.DataFrame
            self.result_fetched_financials : pd.DataFrame


        def register_firm2firm_edge(self) -> SpacialEdgeMatrix:

            # fetch prices data
            self.result_fetched_prices = SQLQuery.fetch_prices()

            # matrix representation of firm prices data is existing or not
            # with CAPM factors column added
            returns_residual_matrix = EdgeMatrixConstructor.Spacial._utils_firm2firm._add_capm_factors_column(
                self.result_fetched_prices, 
                window_size=self.window_size
            )

            # to calc residuals, some tickers may have only NaN
            # so, need to set firm_id_order after calc them
            self.firm_id_order = returns_residual_matrix.columns

            Node_ax1 = NodeSet(self.firm_id_order, "Firm") # Firm Nodes
            Node_ax2 = NodeSet(self.firm_id_order, "Firm") # Firm Nodes

            # sparse_firm2firm_edge_matrix: sparsed edge matrix based torch.Tensor
            for procssing_ratio, week_id, sparse_firm2firm_edge_matrix in EdgeMatrixConstructor.Spacial._utils_firm2firm._iter_prices_adjacent_matrix(
                returns_residual_matrix, 
                self.window_size, 
                self.device
            ):
                if week_id < self.first_week_id:
                    continue

                # display progress
                EdgeMatrixConstructor._utils_common.display_iter(
                    Task_Summary="build spacial firm2firm graph weekly", 
                    week_id=week_id, 
                    procssing_ratio=procssing_ratio,
                    sparse_Node2Node_edge_matrix=sparse_firm2firm_edge_matrix
                )

                # append the matrix representation of the edge(firm - firm) to the list
                self.spacial_firm2firm_edge_list.append((week_id, sparse_firm2firm_edge_matrix))  # 疎行列のみ保持
            return SpacialEdgeMatrix(self.spacial_firm2firm_edge_list, Node_ax1, Node_ax2)


        def register_fin2firm_edge(self) -> SpacialEdgeMatrix:

            # fetch financials data
            # filter Tickers by registered firm_id_order
            self.result_fetched_financials = SQLQuery.fetch_financials(self.firm_id_order.tolist())

            # matrix representation of financials data is existing or not
            financials_exists_matrix = EdgeMatrixConstructor.Spacial._utils_firm2fin._get_financials_exists_matrix(
                self.result_fetched_financials.pivot(index="week_id", columns="Code", values="CurPerType"), 
                self.firm_id_order
            )

            # get the list of week_ids
            weekid_list = financials_exists_matrix.index.tolist()

            Node_Ax1 = NodeSet(self.firm_id_order, "Fin")  # Financial Nodes
            Node_Ax2 = NodeSet(self.firm_id_order, "Firm") # Firm Nodes

            # sparse_fin2firm_edge_matrix: sparsed edge matrix based torch.Tensor
            for procssing_ratio, week_id, sparse_fin2firm_edge_matrix in EdgeMatrixConstructor.Spacial._utils_firm2fin._construct_fin_graph(
                financials_exists_matrix, 
                weekid_list, 
                device=self.device, 
                registerd_codes=self.firm_id_order
            ):

                # filter week_id by user-defined first_week_id
                if week_id < self.first_week_id:
                    continue

                # display progress
                EdgeMatrixConstructor._utils_common.display_iter(
                    Task_Summary="build spacial fin2firm graph weekly", 
                    week_id=week_id, 
                    procssing_ratio=procssing_ratio,
                    sparse_Node2Node_edge_matrix=sparse_fin2firm_edge_matrix
                )

                # append the matrix representation of the edge(fin - firm) to the list
                self.spacial_fin2firm_edge_list.append((week_id, sparse_fin2firm_edge_matrix))  # 疎行列のみ保持
            
            return SpacialEdgeMatrix(self.spacial_fin2firm_edge_list, Node_Ax1, Node_Ax2)


