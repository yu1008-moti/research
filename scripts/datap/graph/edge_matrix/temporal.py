import torch
from typing import Tuple

from scripts.datap.graph.edge_matrix.element import NodeSet

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

