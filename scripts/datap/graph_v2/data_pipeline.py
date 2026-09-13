from torch_geometric.data import HeteroData, InMemoryDataset
from torch_geometric.loader import NeighborLoader, DataLoader

import torch
from torch.utils.data import Subset
from typing import List

from scripts.datap.graph_v2.sql import fetch, insert, create
from scripts.datap.graph_v2 import capm_corr

import duckdb as db
import numpy as np
import pandas as pd

from datetime import datetime as dt
import json
import os
from scripts.datap.graph_v2.cons import rel_sql as cf


def fetch_edge_index(serial_id: int) -> np.ndarray:
    """エッジ情報をデータベースから取得する。（2,E）の形状の DataFrame を返す。
    """
    return fetch.edge_index(serial_id).values.transpose()  # (2,E) の形状に変換する

def fetch_edge_attr(serial_id: int, attr_name: str) -> np.ndarray:
    """エッジの属性情報をデータベースから取得する。（E,）の形状の DataFrame を返す。
    """
    return fetch.edge_attr(serial_id, attr_name=attr_name).values.transpose().flatten()  # (E,) の形状に変換する

def fetch_node_time_id(serial_id: int, attr_name: str) -> np.ndarray:
    """ノードの時間情報をデータベースから取得する。（N,）の形状の DataFrame を返す。
    """
    return fetch.node_attr(serial_id, attr_name="time_id").values.transpose().flatten()  # (N,) の形状に変換する


class preprocess:
    """データを前処理し、graph_node および graph_edge テーブルに格納する。
    """

    def __init__(self, financials_df: pd.DataFrame, prices_df: pd.DataFrame, serial_id: int = 1):
        self.financials_df = financials_df
        self.prices_df = prices_df
        self.serial_id = serial_id  # データベースの識別子を設定する。必要に応じて変更する。
        self.unique_week_id = sorted(set(financials_df['week_id'].unique()).union(set(prices_df['week_id'].unique())))


    @property
    def get_unique_week_id(self) -> List[int]:
        return self.unique_week_id


    ### 1. Related to graph_edge table
    def stock_corr_stock_preprocess(self):
        """銘柄間 CAPM 残差相関エッジを計算し、graph_edge テーブルに格納する。
        """

        prices_df = self.prices_df.copy()

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
            edge_weight_list = []
            observable_time_id = []

            week_id = str(int(week_id))

            src_tk = [firm_id_order[id-1] for id in edge_index[src].cpu().numpy()]
            dst_tk = [firm_id_order[id-1] for id in edge_index[dst].cpu().numpy()]
            src_node_id = [f"stock_{week_id}_{code}" for code in src_tk]
            dst_node_id = [f"stock_{week_id}_{code}" for code in dst_tk]
            edge_id = [f'stock_corr_stock_{week_id}_{src_tk[i]}_{dst_tk[i]}' for i in range(len(src_tk))]
            edge_type = ['stock_corr_stock' for _ in range(len(src_tk))]
            edge_weight_list = edge_weight.cpu().numpy().tolist()
            observable_time_id = [int(week_id) for _ in range(len(src_tk))]

            insert.edge(pd.DataFrame({
                "edge_id":edge_id, 
                "edge_type":edge_type, 
                # "src_node_type":src_node_type, 
                # "dst_node_type":dst_node_type, 
                "src_node_id":src_node_id, 
                "dst_node_id":dst_node_id, 
                "edge_weight_list":edge_weight_list, 
                "observable_time_id":observable_time_id
            }), self.serial_id)

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
            edge_weight_list = []
            observable_time_id = []

            # (src) -> (dst)
            src_node_time_indices = code_df['week_id'].shift(1).values[1:].astype(int).astype(str) # previous
            dst_node_time_indices = code_df['week_id'].values[1:].astype(int).astype(str) # current

            src_node_id = [f'stock_{week_id}_{code}' for week_id in src_node_time_indices]
            dst_node_id = [f'stock_{week_id}_{code}' for week_id in dst_node_time_indices]
            edge_id = [f'stock_corr_stock_{week_id}_{code}_{code}' for week_id in dst_node_time_indices]
            edge_type = ['stock_corr_stock' for _ in range(len(src_node_id))]
            edge_weight_list = [1.0 for _ in range(len(src_node_id))] # 同じ銘柄のエッジは重み1.0とする
            observable_time_id = [int(week_id) for week_id in dst_node_time_indices]

            insert.edge(pd.DataFrame({
                "edge_id":edge_id, 
                "edge_type":edge_type, 
                "src_node_id":src_node_id, 
                "dst_node_id":dst_node_id, 
                "edge_weight_list":edge_weight_list, 
                "observable_time_id":observable_time_id
            }), self.serial_id)


    def statement_prev_statement_preprocess(self):
        """銘柄と決算情報における，報告エッジの作成と graph_edge テーブルへの格納を行う。
        """

        financials_df = self.financials_df.copy()

        for i, code in enumerate(financials_df['Code'].unique(), start=1):
            print(f"\rProcessing code: {code} ({i}/{len(financials_df['Code'].unique())})", end=" ")
            mask :np.ndarray = financials_df['Code'] == code
            code_df = financials_df[mask].copy()

            src_node_id = []
            dst_node_id = []
            edge_id = []
            edge_type = []
            # src_node_type = []
            # dst_node_type = []
            edge_weight_list = []
            observable_time_id = []

            # (src) -> (dst)
            src_node_time_indices = code_df['week_id'].shift(1).values[1:].astype(int).astype(str) # previous
            dst_node_time_indices = code_df['week_id'].values[1:].astype(int).astype(str) # current

            src_node_id = [f'statement_{week_id}_{code}' for week_id in src_node_time_indices]
            dst_node_id = [f'statement_{week_id}_{code}' for week_id in dst_node_time_indices]
            edge_id = [f'statement_prev_statement_{week_id}_{code}_{code}' for week_id in dst_node_time_indices]
            edge_type = ['statement_prev_statement' for _ in range(len(src_node_id))]
            # src_node_type = ['statement' for _ in range(len(src_node_id))]
            # dst_node_type = ['statement' for _ in range(len(src_node_id))]
            edge_weight_list = [1.0 for _ in range(len(src_node_id))]
            observable_time_id = [int(week_id) for week_id in dst_node_time_indices]

            # １バッチでやると，確定で OutOfMemory になるので，1銘柄ごとに insert するquit
            insert.edge(pd.DataFrame({
                "edge_id":edge_id, 
                "edge_type":edge_type, 
                "src_node_id":src_node_id, 
                "dst_node_id":dst_node_id, 
                "edge_weight_list":edge_weight_list, 
                "observable_time_id":observable_time_id
            }), self.serial_id)


    def stock_report_statement_preprocess(self):
        """銘柄と決算情報における，報告エッジの作成と graph_edge テーブルへの格納を行う。
        """

        financials_df = self.financials_df.copy()

        for code in financials_df['Code'].unique():
            mask :np.ndarray = financials_df['Code'] == code
            code_df = financials_df[mask].copy()

            src_node_id = []
            dst_node_id = []
            edge_id = []
            edge_type = []
            edge_weight_list = []
            observable_time_id = []

            # (src) -> (dst)
            src_node_time_indices = code_df['week_id'].values.astype(int).astype(str) # current
            dst_node_time_indices = code_df['week_id'].values.astype(int).astype(str) # current

            src_node_id = [f'statement_{week_id}_{code}' for week_id in dst_node_time_indices]
            dst_node_id = [f'stock_{week_id}_{code}' for week_id in src_node_time_indices]
            edge_id = [f'statement_report_stock_{week_id}_{code}_{code}' for week_id in dst_node_time_indices]
            edge_type = ['statement_report_stock' for _ in range(len(src_node_id))]
            edge_weight_list = [1.0 for _ in range(len(src_node_id))]
            observable_time_id = [int(week_id) for week_id in dst_node_time_indices]

            insert.edge(pd.DataFrame({
                "edge_id":edge_id, 
                "edge_type":edge_type, 
                "src_node_id":src_node_id, 
                "dst_node_id":dst_node_id, 
                "edge_weight_list":edge_weight_list, 
                "observable_time_id":observable_time_id
            }), self.serial_id)


    ### 2. Related to graph_node table
    def node_id_define(self):
        """銘柄ノードと決算情報ノードの node_id を定義する。
        """

        using_df_list = [
            (self.financials_df.copy(), "statement"), 
            (self.prices_df.copy(), "stock")
        ]

        for i, (df, node_type) in enumerate(using_df_list, start=1):

            print(f"Processing node_type: {node_type} ({i}/{len(using_df_list)})")

            # 銘柄ノードの node_id を定義する
            node_id = df.apply(lambda row: f'{node_type}_{str(int(row["week_id"]))}_{row["Code"]}', axis=1)
            # 銘柄のティッカーを取得する
            tickers = df['Code'].values

            # TODO: ターゲットノードかどうかを示す is_target を定義する
            is_target = []
            if node_type == "stock":
                is_target = (df["Mkt"] == "0000") | (df["Mkt"] == "0500")
                is_target = is_target.astype(bool).tolist()
            else:
                is_target = [False for _ in range(len(df))]

            node_type = [node_type for _ in range(len(df))]
            time_indices = df['week_id'].values.astype(int)

            # node_id, ticker, node_type, observable_time_id を graph_node テーブルに格納する
            insert.node(pd.DataFrame({
                "node_id": node_id,
                "is_target": is_target,
                "ticker": tickers,
                "node_type": node_type,
                "time_id": time_indices
            }), self.serial_id)


    ### 3. Related to node_feats table
    def node_feats_define(self):
        """銘柄ノードと決算情報ノードの特徴量を定義する。
        バッチ処理によって， node_id, feats, feats_num を graph_node テーブルに格納する。
        1. 銘柄ノードの特徴量は，株価データの各列を使用する。
        2. 決算情報ノードの特徴量は，財務諸表データの各列を使用する。
        3. バッチサイズは 1000 とする。
        4. node_id, feats, feats_num を graph_node テーブルに格納する。
        """

        using_df_list = [
            (self.financials_df.copy(), "statement"), 
            (self.prices_df.copy(), "stock")
        ]

        for i, (df, node_type) in enumerate(using_df_list, start=1):
            if 'week_id' not in df.columns:
                raise ValueError("DataFrame must contain 'week_id' column.")
            if 'Code' not in df.columns:
                raise ValueError("DataFrame must contain 'Code' column.")

            print(f"Processing node_type: {node_type} ({i}/{len(using_df_list)})")

            # duckdb がサポートしていないdatetime型の列を文字列に変換する
            if 'CurFYEn' in df.columns:
                df['CurFYEn'] = df['CurFYEn'].astype(str)

            for batch_start in range(0, len(df), 1000):
                batch_end = min(batch_start + 1000, len(df))
                print(f"\rProcessing batch: {batch_start} to {batch_end} ({i}/{len(using_df_list)})", end="")

                df_batch = df.iloc[batch_start:batch_end]

                # ノードIDを生成する
                batch_node_id = df_batch.apply(
                    lambda row: f'{node_type}_{str(int(row["week_id"]))}_{row["Code"]}', axis=1
                )

                df_batch = df_batch.drop(columns=['week_id', 'Code'])

                # 特徴量を JSON 形式で格納するために，DataFrame の各行を辞書に変換し，JSON 文字列に変換する
                batch_feats = df_batch.assign(
                    payload = df_batch
                    .apply(lambda row: row.to_dict(), axis=1)
                    .map(json.dumps)
                )[['payload']].values.flatten()

                # 特徴量の数を計算する
                batch_feats_num = [df_batch.shape[1] for _ in range(len(df_batch))]

                # node_id, ticker, node_type, observable_time_id を graph_node テーブルに格納する
                insert.feats(pd.DataFrame({
                    "node_id": batch_node_id,
                    "feats": batch_feats,
                    "feats_num": batch_feats_num,
                }), self.serial_id)
            print()  # 改行


    ### 4. Insertion graph_node and graph_edge to tables
    def insert_to_graph_info_table(self):
        """データベースにノード情報とエッジ情報を登録する。
        """
        edge_func_list = [
            # エッジ情報
            self.statement_prev_statement_preprocess,
            self.stock_report_statement_preprocess,
            self.stock_corr_stock_preprocess,
            # ノード情報
            self.node_id_define,
            # 特徴量情報
            self.node_feats_define
        ]

        # データベースにグラフ情報を登録する
        for func in edge_func_list:
            now = dt.now()
            func()
            print("preprocess time", dt.now() - now)


class graphDataSet(InMemoryDataset):
    """
    PyG の InMemoryDataset を継承したクラスで，グラフデータをメモリ上に保持する。
    """

    def __init__(self, root, transform=None, pre_transform=None, serial_id: int = 1, train_test_split_per: float = 0.6, train_val_split_per: float = 0.2):
        super().__init__(root, transform, pre_transform)
        self.load(self.processed_paths[0])
        self.serial_id = serial_id  # データベースの識別子を設定する。必要に応じて変更する。
        self.train_test_split_per = train_test_split_per
        self.train_val_split_per = train_val_split_per

    @property
    def raw_file_names(self) -> List[str]:
        return []

    @property
    def processed_file_names(self) -> List[str]:
        return [
            f"data_{self.serial_id}_train.pt",
            f"data_{self.serial_id}_val.pt",
            f"data_{self.serial_id}_test.pt"
        ]

    @property
    def num_classes(self) -> int:
        return 2  # 2クラス分類問題を想定している場合

    @property
    def node_types(self) -> List[str]:
        return ["stock", "statement"]

    def download(self) -> None:
        pass

    def process(self) -> None:
        """データを処理し、HeteroData オブジェクトを作成する。
        """

        # シリアルIDに対応するデータベースが無い => 新たに作成する
        if not os.path.exists(cf.PATH_GRAPHINFO_DB.safe_substitute(serial_id=self.serial_id)):
            # データベースが存在しない場合は、graph_info テーブルを作成する
            create.graph_info(self.serial_id)

            # データを前処理する
            pp = preprocess(
                financials_df = fetch.financials(), 
                prices_df = fetch.prices(), 
                serial_id = self.serial_id
            )
            pp.insert_to_graph_info_table()

            data_list: List[HeteroData] = []

            observable_time_id = fetch_edge_attr(self.serial_id, attr_name="observable_time_id")
            edge_index = fetch_edge_index(self.serial_id)
            edge_type = fetch_edge_attr(self.serial_id, attr_name="edge_type")
            edge_type_names = list(set(edge_type))

            for week_id in pp.get_unique_week_id:
                data = HeteroData()
                for edge_type_name in edge_type_names:
                    idx = np.where((observable_time_id <= week_id) & (edge_type == edge_type_name))[0]
                    src_t, rel, dst_t = edge_type_name.split("_")[:3]
                    data[src_t, rel, dst_t].edge_index = edge_index[:, idx]
                    data[src_t, rel, dst_t].edge_weight = fetch_edge_attr(self.serial_id, attr_name="edge_weight")[idx]
                    data[src_t, rel, dst_t].edge_observable = fetch_edge_attr(self.serial_id, attr_name="observable_time_id")[idx]
                data_list.append(data)

            train_separate_idx = int(self.train_test_split_per * len(data_list))
            val_separate_idx = int((self.train_test_split_per + self.train_val_split_per) * len(data_list))

            range_dict = {
                "train": ((0, train_separate_idx), 0),
                "val"  : ((train_separate_idx, val_separate_idx), 1),
                "test" : ((val_separate_idx, len(data_list)), 2)
            }

            for split_name, ((start, end), id) in range_dict.items():
                print(f"Processing {split_name} data: {start} to {end}")
                self.save(data_list[start:end], self.processed_paths[id])


def get_dataloader(batch_size: int = 32):
    """HGTLoader を使用して、グラフデータをロードする。
    """
    dataset = graphDataSet(root="scripts/datap/graph_v2/DS", serial_id=1)

    dataset_train: List[HeteroData] = torch.load(dataset.processed_paths[0])
    dataset_val: List[HeteroData] = torch.load(dataset.processed_paths[1])
    dataset_test: List[HeteroData] = torch.load(dataset.processed_paths[2])

    train_loader = DataLoader(
        dataset_train,
        batch_size=batch_size, 
        shuffle=True
    )
    val_loader = DataLoader(
        dataset_val, 
        batch_size=batch_size, 
        shuffle=True
    )
    test_loader = DataLoader(
        dataset_test, 
        batch_size=batch_size, 
        shuffle=True
    )

    return train_loader, val_loader, test_loader

def get_neighbor_loader(data: HeteroData):
    """NeighborLoader を使用して、グラフデータをロードする。
    """

    loader = NeighborLoader(
        data,
        num_neighbors={
            ('stock', 'corr', 'stock'): [10, 10],
            ('statement', 'prev', 'statement'): [10, 10],
            ('statement', 'report', 'stock'): [10, 10]
        },
        input_nodes=('stock', data['stock'].node_id),
        shuffle=True
    )

    return loader


def mock_code():
    train_loader, val_loader, test_loader = get_dataloader(batch_size=32)
    for data in train_loader:
        for neighbor_data in get_neighbor_loader(data):
            print(neighbor_data)
        for data in val_loader:
            for neighbor_data in get_neighbor_loader(data):
                print(neighbor_data)

    for data in test_loader:
        for neighbor_data in get_neighbor_loader(data):
            print(neighbor_data)