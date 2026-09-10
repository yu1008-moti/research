from torch_geometric.data import HeteroData, InMemoryDataset
import torch
from typing import List

from scripts.datap.graph_v2.sql import fetch
from scripts.datap.graph_v2 import capm_corr


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
        prices_df = fetch.prices()

        # 銘柄間 CAPM 残差相関エッジ (週 ID -> (edge_index, edge_weight))
        firm_corr = capm_corr.build_firm_corr_edges(prices_df)
        firm_id_order = firm_corr.firm_id_order
        num_firms = len(firm_id_order)

        # 週ごとに 1 つの HeteroData を作り、時系列スナップショットとして格納する
        data_list: List[HeteroData] = []
        for week_id, (edge_index, edge_weight) in sorted(firm_corr.edges.items()):
            data = HeteroData()
            data["firm"].num_nodes = num_firms
            data["firm"].node_id = torch.arange(num_firms)
            data["firm", "corr", "firm"].edge_index = edge_index
            data["firm", "corr", "firm"].edge_weight = edge_weight
            data["firm", "corr", "firm"].edge_attr = edge_weight.unsqueeze(-1)
            data.week_id = int(week_id)
            data_list.append(data)

        if self.pre_filter is not None:
            data_list = [d for d in data_list if self.pre_filter(d)]
        if self.pre_transform is not None:
            data_list = [self.pre_transform(d) for d in data_list]

        self.save(data_list, self.processed_paths[0])
