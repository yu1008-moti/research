from torch_geometric.data import HeteroData, InMemoryDataset
import torch
from typing import List

from scripts.datap.graph_v2.sql import fetch, insert
from scripts.datap.graph_v2 import capm_corr

import duckdb as db
import numpy as np
import pandas as pd



def stock_corr_stock_preprocess(prices_df: pd.DataFrame):
    """銘柄間 CAPM 残差相関エッジを計算し、graph_edge テーブルに格納する。
    """
    src, dst = 0, 1

    # 銘柄間 CAPM 残差相関エッジ (週 ID -> (edge_index, edge_weight))
    firm_corr = capm_corr.build_firm_corr_edges(prices_df)
    firm_id_order = firm_corr.firm_id_order

    # 銘柄間 CAPM 残差相関エッジを graph_edge テーブルに格納する
    for week_id, (edge_index, edge_weight) in sorted(firm_corr.edges.items()):

        src_tk = []
        dst_tk = []
        src_node_id = []
        dst_node_id = []
        edge_id = []
        edge_type = []
        src_node_type = []
        dst_node_type = []
        edge_weight_list = []
        observable_time_id = []

        src_tk = [firm_id_order[id-1] for id in edge_index[src].cpu().numpy()]
        dst_tk = [firm_id_order[id-1] for id in edge_index[dst].cpu().numpy()]
        src_node_id = [f"stock_{week_id}_{code}" for code in src_tk]
        dst_node_id = [f"stock_{week_id}_{code}" for code in dst_tk]
        edge_id = [f'stock_corr_stock_{week_id}_{src_tk[i]}_{dst_tk[i]}' for i in range(len(src_tk))]
        edge_type = ['stock_corr_stock' for _ in range(len(src_tk))]
        src_node_type = ['stock' for _ in range(len(src_tk))]
        dst_node_type = ['stock' for _ in range(len(src_tk))]
        edge_weight_list = edge_weight.cpu().numpy().tolist()
        observable_time_id = [week_id for _ in range(len(src_tk))]

        insert.edge(pd.DataFrame({
            "edge_id":edge_id, 
            "edge_type":edge_type, 
            "src_node_type":src_node_type, 
            "dst_node_type":dst_node_type, 
            "src_node_id":src_node_id, 
            "dst_node_id":dst_node_id, 
            "edge_weight_list":edge_weight_list, 
            "observable_time_id":observable_time_id
        }))

    # 同じ銘柄は1-step前の銘柄と現時点の銘柄の間にエッジを作る
    for code in prices_df['Code'].unique():
        mask :np.ndarray = prices_df['Code'] == code
        code_df = prices_df[mask].copy()

        src_tk = []
        dst_tk = []
        src_node_id = []
        dst_node_id = []
        edge_id = []
        edge_type = []
        src_node_type = []
        dst_node_type = []
        edge_weight_list = []
        observable_time_id = []

        # (src) -> (dst)
        src_node_time_indices = code_df['week_id'].shift(1).values[1:] # previous
        dst_node_time_indices = code_df['week_id'].values[1:] # current

        src_node_id = [f'stock_{int(week_id)}_{code}' for week_id in src_node_time_indices]
        dst_node_id = [f'stock_{int(week_id)}_{code}' for week_id in dst_node_time_indices]
        edge_id = [f'stock_corr_stock_{int(week_id)}_{code}_{code}' for week_id in dst_node_time_indices]
        edge_type = ['stock_corr_stock' for _ in range(len(src_node_id))]
        src_node_type = ['stock' for _ in range(len(src_node_id))]
        dst_node_type = ['stock' for _ in range(len(src_node_id))]
        edge_weight_list = [1.0 for _ in range(len(src_node_id))] # 同じ銘柄のエッジは重み1.0とする
        observable_time_id = [week_id for week_id in dst_node_time_indices]

        insert.edge(pd.DataFrame({
            "edge_id":edge_id, 
            "edge_type":edge_type, 
            "src_node_type":src_node_type, 
            "dst_node_type":dst_node_type, 
            "src_node_id":src_node_id, 
            "dst_node_id":dst_node_id, 
            "edge_weight_list":edge_weight_list, 
            "observable_time_id":observable_time_id
        }))


def statement_prev_statement_preprocess(financials_df: pd.DataFrame):
    """銘柄と決算情報における，報告エッジの作成と graph_edge テーブルへの格納を行う。
    """

    for i, code in enumerate(financials_df['Code'].unique(), start=1):
        print(f"\rProcessing code: {code} ({i}/{len(financials_df['Code'].unique())})", end=" ")
        mask :np.ndarray = financials_df['Code'] == code
        code_df = financials_df[mask].copy()

        src_node_id = []
        dst_node_id = []
        edge_id = []
        edge_type = []
        src_node_type = []
        dst_node_type = []
        edge_weight_list = []
        observable_time_id = []

        # (src) -> (dst)
        src_node_time_indices = code_df['week_id'].shift(1).values[1:] # previous
        dst_node_time_indices = code_df['week_id'].values[1:] # current

        src_node_id = [f'statement_{int(week_id)}_{code}' for week_id in src_node_time_indices]
        dst_node_id = [f'statement_{int(week_id)}_{code}' for week_id in dst_node_time_indices]
        edge_id = [f'statement_prev_statement_{int(week_id)}_{code}_{code}' for week_id in dst_node_time_indices]
        edge_type = ['statement_prev_statement' for _ in range(len(src_node_id))]
        src_node_type = ['statement' for _ in range(len(src_node_id))]
        dst_node_type = ['statement' for _ in range(len(src_node_id))]
        edge_weight_list = [1.0 for _ in range(len(src_node_id))]
        observable_time_id = [week_id for week_id in dst_node_time_indices]

        # １バッチでやると，確定で OutOfMemory になるので，1銘柄ごとに insert するquit
        insert.edge(pd.DataFrame({
            "edge_id":edge_id, 
            "edge_type":edge_type, 
            "src_node_type":src_node_type, 
            "dst_node_type":dst_node_type, 
            "src_node_id":src_node_id, 
            "dst_node_id":dst_node_id, 
            "edge_weight_list":edge_weight_list, 
            "observable_time_id":observable_time_id
        }))


def stock_report_statement_preprocess(financials_df: pd.DataFrame):
    """銘柄と決算情報における，報告エッジの作成と graph_edge テーブルへの格納を行う。
    """
    for code in financials_df['Code'].unique():
        mask :np.ndarray = financials_df['Code'] == code
        code_df = financials_df[mask].copy()

        src_node_id = []
        dst_node_id = []
        edge_id = []
        edge_type = []
        src_node_type = []
        dst_node_type = []
        edge_weight_list = []
        observable_time_id = []

        # (src) -> (dst)
        src_node_time_indices = code_df['week_id'].values # current
        dst_node_time_indices = code_df['week_id'].values # current

        src_node_id = [f'stock_{int(week_id)}_{code}' for week_id in src_node_time_indices]
        dst_node_id = [f'statement_{int(week_id)}_{code}' for week_id in dst_node_time_indices]
        edge_id = [f'stock_report_statement_{int(week_id)}_{code}_{code}' for week_id in dst_node_time_indices]
        edge_type = ['stock_report_statement' for _ in range(len(src_node_id))]
        src_node_type = ['stock' for _ in range(len(src_node_id))]
        dst_node_type = ['statement' for _ in range(len(src_node_id))]
        edge_weight_list = [1.0 for _ in range(len(src_node_id))]
        observable_time_id = [week_id for week_id in dst_node_time_indices]

        insert.edge(pd.DataFrame({
            "edge_id":edge_id, 
            "edge_type":edge_type, 
            "src_node_type":src_node_type, 
            "dst_node_type":dst_node_type, 
            "src_node_id":src_node_id, 
            "dst_node_id":dst_node_id, 
            "edge_weight_list":edge_weight_list, 
            "observable_time_id":observable_time_id
        }))


def node_id_define(financials_df: pd.DataFrame, prices_df: pd.DataFrame):
    """銘柄ノードと決算情報ノードの node_id を定義する。
    """
    # 銘柄ノードの node_id を定義する
    stock_node_id = prices_df.apply(lambda row: f'stock_{row["week_id"]}_{row["Code"]}', axis=1)
    stock_tickers = prices_df['Code'].values,
    stock_node_type = ['stock' for _ in range(len(prices_df))]
    stock_time_indices = prices_df['week_id'].values

    # 決算情報ノードの node_id を定義する
    statement_node_id = financials_df.apply(lambda row: f'statement_{row["week_id"]}_{row["Code"]}', axis=1)
    statement_tickers = financials_df['Code'].values,
    statement_node_type = ['statement' for _ in range(len(financials_df))]
    statement_time_indices = financials_df['week_id'].values

    # node_id, ticker, node_type, observable_time_id を graph_node テーブルに格納する
    insert.node(pd.DataFrame({
        "node_id": stock_node_id,
        "ticker": stock_tickers,
        "node_type": stock_node_type,
        "time_id": stock_time_indices
    }))

    insert.node(pd.DataFrame({
        "node_id": statement_node_id,
        "ticker": statement_tickers,
        "node_type": statement_node_type,
        "time_id": statement_time_indices
    }))


class graphDataSet(InMemoryDataset):
    """週次のヘテロググラフ (Firm ノード) データセット。

    現状のエッジは ``('firm', 'corr', 'firm')`` のみ:
    銘柄間の CAPM 残差リターンのローリング相関が閾値を超えたペアを
    週ごとに 1 グラフとして格納する (graph_v1 から移植した機能)。
    """

    def __init__(self, root, transform=None, pre_transform=None):
        super().__init__(root, transform, pre_transform)
        self.load(self.processed_paths[0])

    @property
    def raw_file_names(self) -> List[str]:
        return []

    @property
    def processed_file_names(self) -> List[str]:
        return ["data.pt"]

    def download(self) -> None:
        pass

    def process(self) -> None:
        """データを処理し、HeteroData オブジェクトを作成する。
        """

        financials_df = fetch.financials()
        prices_df = fetch.prices()

        node_id_define(financials_df, prices_df)
        statement_prev_statement_preprocess(financials_df)
        stock_report_statement_preprocess(financials_df)
        stock_corr_stock_preprocess(prices_df)

        data = HeteroData()

        self.save([data], self.processed_paths[0])
