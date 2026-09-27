"""単一の HeteroData を保持する PyG InMemoryDataset (`graphDataSet`)。

data_pipeline.py から分離。graph_info DB が未構築ならまず `preprocess` で構築し、
その後 graph_io.* を使って全ノード・全エッジを読み出し、HeteroData に組み立てる。
"""

from __future__ import annotations

import importlib
import os
from typing import Dict, List, Tuple

import numpy as np
import torch
from torch_geometric.data import HeteroData, InMemoryDataset

from scripts.datap.graph.cons import rel_sql as cf
from scripts.datap.graph.feature_encoding import DEFAULT_VOCAB_DIR, LABEL_COLUMNS, TORCH_FLOAT_DTYPE
from scripts.datap.graph.graph_io import (
    build_node_id_to_idx,
    fetch_edge_attr,
    fetch_edge_index,
    fetch_node_table,
    map_edge_ids_to_idx,
)
from scripts.datap.graph.preprocess import preprocess
from scripts.datap.graph.sql import create, fetch

# --------------------------------------------------------------------------
# 逆エッジを自動生成したい関係。
# {(src, rel, dst): 逆方向の relation 名}
# 対称な関係（相関エッジなど）はここに入れない。
# --------------------------------------------------------------------------
REVERSE_RELATIONS: Dict[Tuple[str, str, str], str] = {
    ("statement", "report", "stock"): "rev_report",
    ("stock", "derivative", "option"): "rev_derivative",
    ("stock", "derivative", "future"): "rev_derivative",
}

_SAFE_GLOBALS_REGISTERED = False


def _allow_numpy_globals_for_torch_load() -> None:
    """torch.load(weights_only=True) が HeteroData 内の numpy 配列
    (node_str_id など文字列配列) を復元できるよう、安全なグローバル関数として
    許可リストに登録する。

    ★ ここで許可しているのは「自分自身の前処理が書き出した.ptファイルの復元に
    必要な、numpyの内部関数」のみ。他者から受け取った信頼できないファイルの
    読み込みにこの安全性を流用しないこと。
    """
    global _SAFE_GLOBALS_REGISTERED
    if _SAFE_GLOBALS_REGISTERED:
        return

    # np.core.multiarray / np._core.multiarray への直接の属性アクセスは
    # numpyの型スタブが公開していないため Pylance が誤検知する。
    # importlib + getattr(文字列) による動的アクセスに統一して回避する。
    module_name = "numpy._core.multiarray" if hasattr(np, "_core") else "numpy.core.multiarray"
    multiarray_module = importlib.import_module(module_name)
    reconstruct = getattr(multiarray_module, "_reconstruct")

    torch.serialization.add_safe_globals([reconstruct, np.ndarray, np.dtype])
    _SAFE_GLOBALS_REGISTERED = True


class graphDataSet(InMemoryDataset):
    """全期間・全銘柄・全ノードタイプを含む「単一の」HeteroData を保持するデータセット。

    train/val/test の分割はここでは行わない（get_loaders 側でマスクとして行う）。
    """

    def __init__(self, root, transform=None, pre_transform=None, serial_id: int = 1,
                 vocab_dir: str = DEFAULT_VOCAB_DIR):
        self.serial_id = serial_id
        self.vocab_dir = vocab_dir
        _allow_numpy_globals_for_torch_load()  # weights_only=True での復元を可能にする
        super().__init__(root, transform, pre_transform)
        self.load(self.processed_paths[0])

    @property
    def raw_file_names(self) -> List[str]:
        return []

    @property
    def processed_file_names(self) -> List[str]:
        # 単一グラフのみを保持するため、ファイルは1つでよい
        return [f"data_{self.serial_id}_full.pt"]

    @property
    def num_classes(self) -> int:
        return 2

    def download(self) -> None:
        pass

    def _ensure_db_built(self) -> None:
        """raw データの DB 登録（前処理）が未実行なら実行する。"""
        db_path = cf.PATH_GRAPHINFO_DB.safe_substitute(serial_id=self.serial_id)
        if os.path.exists(db_path):
            return

        create.graph_info(self.serial_id)
        pp = preprocess(
            financials_df=fetch.financials(),
            prices_df=fetch.prices(),
            options_df=fetch.options(),
            futures_df=fetch.futures(),
            serial_id=self.serial_id,
            vocab_dir=self.vocab_dir,
        )
        pp.insert_to_graph_info_table()

    def _node_str_id_path(self, node_type: str) -> str:
        """node_str_id を保存する .npy ファイルのパス。

        HeteroData の中には入れず、別ファイルとして保存する
        （NeighborLoader が全ノード属性を自動でテンソル化しようとするため、
        文字列配列を data[node_type] に直接持たせると
        TypeError: can't convert np.ndarray of type numpy.str_ になる）。
        """
        return os.path.join(self.processed_dir, f"node_str_id_{self.serial_id}_{node_type}.npy")

    def load_node_str_id(self, node_type: str) -> np.ndarray:
        """指定 node_type の node_str_id 配列をロードする。

        使い方（学習ループ内でバッチの正体を特定したい場合）:
            global_idx = batch['stock'].n_id.numpy()  # NeighborLoaderが自動付与
            str_ids = dataset.load_node_str_id('stock')[global_idx]
        """
        return np.load(self._node_str_id_path(node_type), allow_pickle=False)

    def _build_full_graph(self) -> HeteroData:
        """DB から全エッジ・全ノードを取得し、単一の HeteroData を構築する。"""
        data = HeteroData()

        # 1. 先にノード側を読み込み、node_id文字列 -> ローカル整数インデックス の
        #    辞書を node_type ごとに作っておく（エッジ側の整数化に必要なため）
        node_id_to_idx: Dict[str, Dict[str, int]] = {}
        for node_type in ["stock", "statement", "option", "future"]:
            node_table = fetch_node_table(self.serial_id, node_type)
            data[node_type].x = torch.tensor(node_table["x"], dtype=TORCH_FLOAT_DTYPE)
            data[node_type].cat_x = torch.tensor(node_table["cat_x"], dtype=torch.long)   # (N, カテゴリ列数)
            data[node_type].date_x = torch.tensor(node_table["date_x"], dtype=TORCH_FLOAT_DTYPE)  # (N, 日付列数)
            # 目的変数（例: stock の y / y_valid）。x とは別テンソルとして持たせる
            # （LABEL_COLUMNS[node_type] が空なら label_x は (N, 0) で何も生えない）
            for label_idx, label_col in enumerate(LABEL_COLUMNS.get(node_type, [])):
                data[node_type][label_col] = torch.tensor(
                    node_table["label_x"][:, label_idx], dtype=TORCH_FLOAT_DTYPE
                )
            data[node_type].is_target = torch.tensor(node_table["is_target"], dtype=torch.bool)
            data[node_type].time_id = torch.tensor(node_table["time_id"], dtype=torch.long)
            # 文字列IDは HeteroData に入れず .npy として別保存する（理由は _node_str_id_path 参照）
            os.makedirs(self.processed_dir, exist_ok=True)
            np.save(self._node_str_id_path(node_type), node_table["node_str_id"])

            node_id_to_idx[node_type] = build_node_id_to_idx(node_table["node_str_id"])

        # 2. エッジ側（まだ文字列 node_id のまま）を取得
        edge_src_str, edge_dst_str = fetch_edge_index(self.serial_id)  # それぞれ (E,) の文字列配列
        edge_type = fetch_edge_attr(self.serial_id, "edge_type")
        edge_weight = fetch_edge_attr(self.serial_id, "edge_weight")
        edge_time = fetch_edge_attr(self.serial_id, "observable_time_id")

        edge_type_names = sorted(set(edge_type))
        for edge_type_name in edge_type_names:
            src_t, rel, dst_t = edge_type_name.split("__")
            idx = np.where(edge_type == edge_type_name)[0]

            # 文字列 node_id -> 整数インデックス に変換してから tensor化する
            edge_index_int = map_edge_ids_to_idx(
                edge_src_str[idx], edge_dst_str[idx],
                node_id_to_idx[src_t], node_id_to_idx[dst_t],
            )

            data[src_t, rel, dst_t].edge_index = torch.tensor(edge_index_int, dtype=torch.long)
            data[src_t, rel, dst_t].edge_weight = torch.tensor(edge_weight[idx], dtype=TORCH_FLOAT_DTYPE)
            data[src_t, rel, dst_t].edge_time = torch.tensor(edge_time[idx], dtype=torch.long)

            # 逆エッジを必要とする関係なら追加する
            key = (src_t, rel, dst_t)
            if key in REVERSE_RELATIONS:
                rev_rel = REVERSE_RELATIONS[key]
                rev_edge_index = edge_index_int[[1, 0], :]  # src/dst を入れ替え
                data[dst_t, rev_rel, src_t].edge_index = torch.tensor(rev_edge_index, dtype=torch.long)
                data[dst_t, rev_rel, src_t].edge_weight = torch.tensor(edge_weight[idx], dtype=TORCH_FLOAT_DTYPE)
                data[dst_t, rev_rel, src_t].edge_time = torch.tensor(edge_time[idx], dtype=torch.long)

        return data

    def process(self) -> None:
        self._ensure_db_built()
        data = self._build_full_graph()
        self.save([data], self.processed_paths[0])
