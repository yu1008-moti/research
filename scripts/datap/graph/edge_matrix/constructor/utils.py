import torch
from typing import List, Optional, Any

from scripts.datap.graph.cons import print_constants as pc



class u_common:
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
            # sentence_stack.insert(0, f'\r{Constants.CLEAR}')
            sentence_stack.insert(0, '\r')
            end = " "
        elif procssing_ratio < 1.0:
            # sentence_stack.insert(0, f'\r{Constants.CLEAR}')
            sentence_stack.insert(0, '\r')
            end = " "
        else:
            end = "\n"

        sentence_stack.append(f"Processing [{pc.MAGENTA}{Task_Summary}{pc.RESET}] ")
        
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
            f"Title: [{pc.MAGENTA}{note_title}{pc.RESET}]: ",
            f"{content}"
        )