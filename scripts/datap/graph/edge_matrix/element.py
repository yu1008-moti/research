import pandas as pd
from typing import Optional

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


    def get_idx_corresponding_node_id(self, node_id:str) -> Optional[int]:
        """指定されたノードIDに対応するインデックスを取得するメソッド
        Args:
            node_id (str): 取得するノードID
        Returns:
            Optional[int]: 指定されたノードIDに対応するインデックス、存在しない場合はNone
        """
        try:
            idx = self.node_order.get_loc(node_id)
            if isinstance(idx, int):
                return idx
            else:
                return None
        except KeyError:
            return None 
