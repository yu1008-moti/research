import torch
from typing import List, Tuple, Optional
import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
from scipy.cluster.hierarchy import distance

from scripts.datap.graph.edge_matrix.element import NodeSet


__all__ = ['SpacialEdgeMatrix']


class _utils:

    @staticmethod
    def _binary_Search_edge_matrix(
            week_id:int,
            spacial_node2node_edge_list: List[Tuple[int, torch.Tensor]]
        ) -> Optional[torch.Tensor]:
        """指定された週IDに対応するエッジ行列を二分探索で取得するメソッド
        Args:
            week_id (int): 取得する週ID
        Returns:
            Optional[torch.Tensor]: 指定された週IDに対応するエッジ行列、存在しない場合はNone
        """
        left, right = 0, len(spacial_node2node_edge_list) - 1

        while left <= right:
            mid = (left + right) // 2
            mid_week_id, mid_edge_matrix = spacial_node2node_edge_list[mid]

            if mid_week_id == week_id:
                return mid_edge_matrix
            elif mid_week_id < week_id:
                left = mid + 1
            else:
                right = mid - 1

        return None

    @staticmethod
    def uniform_layout(G: nx.Graph, alpha=0.1, n_iter=None, seed=None, **kwargs):
        """グラフのノードを均一に配置するためのレイアウト計算関数
        (https://qiita.com/okumakito/items/902152a66d646f61d7ed より拝借)

        Args:
            G (nx.Graph): NetworkXのグラフオブジェクト
            alpha (float, optional): ノードの移動量を制御するパラメータ. Defaults to 0.1.
            n_iter (int, optional): レイアウト計算の反復回数. Defaults to None.
            seed (int, optional): 乱数シード. Defaults to None.
        Returns:
            dict: ノードIDをキー、座標を値とする辞書
        """
        pos = nx.spring_layout(G, seed=seed, **kwargs)
        X = np.array(list(pos.values()))
        if n_iter == None:
            n_iter = 10 * len(G)
        for _ in range(n_iter):
            D = distance.squareform(distance.pdist(X))
            np.fill_diagonal(D, None)
            X += alpha * (X - X[np.nanargmin(D, axis=0)])
            X = X.clip(-1,1)
        return dict(zip(pos.keys(), X))


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


    def get_nums_of_edges(self, week_id:int, node_id:str) -> Optional[torch.Tensor]:
        """指定された週IDに対応するエッジ行列を取得するメソッド
        Args:
            week_id (int): 取得する週ID
            node_id (str): 取得するノードID
        Returns:
            Optional[torch.Tensor]: 指定された週IDに対応するエッジ行列、存在しない場合はNone
        """
        edge_matrix = _utils._binary_Search_edge_matrix(week_id, self.spacial_node2node_edge_list)
        col_id_correspoding_node_id = self.node2.get_idx_corresponding_node_id(node_id)

        if edge_matrix is None:
            print(f"\rNo edge matrix found for week_id: {week_id}", end="")
            return None
        
        if col_id_correspoding_node_id is None:
            print(f"\rNo node_id found: {node_id}", end="")
            return None

        edge_matrix = edge_matrix.to_dense()[col_id_correspoding_node_id].cpu().numpy()

        edge_nums_sum = np.where(edge_matrix>0, 1, 0).sum()

        return edge_nums_sum


    def visualize_graph(self, week_id:int, node_id:str, radius:int=4) -> None:
        """指定された週IDに対応するグラフを可視化するメソッド
        Args:
            week_id (int): 可視化する週ID
            node_id (str): 可視化するノードID
            radius (int): エゴグラフの半径
        """
        # Find the edge matrix for the specified week_id
        edge_matrix = _utils._binary_Search_edge_matrix(week_id, self.spacial_node2node_edge_list)


        if edge_matrix is None:
            print(f"No edge matrix found for week_id: {week_id}")
            return

        # Convert sparse tensor to dense for visualization
        dense_matrix = edge_matrix.to_dense().cpu().numpy()

        # Create a graph from the adjacency matrix
        G = nx.from_numpy_array(dense_matrix)  # Ensure node_order is a list for indexing

        G = nx.relabel_nodes(G, {i: self.node1.node_order[i] for i in range(len(self.node1.node_order))})  # Relabel nodes with actual node IDs
        
        if node_id is not None:
            G: nx.Graph = nx.ego_graph(G, node_id, radius=radius)  # Get the ego graph for the specified node

        pos = _utils.uniform_layout(G, seed=42)  # Use uniform layout for better visualization

        # change color of node_id to red
        node_colors = ['red' if node == node_id else 'lightblue' for node in G.nodes()]

        # change color of edges that have edges with node_id to orange
        edge_colors = ['orange' if (u == node_id or v == node_id) and (u, v) in G.edges() else "#B6B6B6" for u, v in G.edges()]

        # print adjacent nodes of node_id
        adjacent_nodes = list(G.neighbors(node_id))
        print(f"Adjacent nodes of {node_id}: {adjacent_nodes}")

        # Draw the graph
        plt.figure(figsize=(10, 10))
        nx.draw(G, pos=pos, with_labels=True, node_color=node_colors, edge_color=edge_colors, node_size=500, font_size=10)
        plt.title(f"Graph Visualization for Week ID: {week_id}")
        plt.show()
