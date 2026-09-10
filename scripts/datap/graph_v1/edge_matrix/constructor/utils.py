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
        sentence_stack.append('\r')

        if procssing_ratio is None:
            end = " "
        elif procssing_ratio == 1.0:
            end = "\n"
        else:
            end = " "

        sentence_stack.append(f"TASK [{pc.MAGENTA}{Task_Summary}{pc.RESET}] ")
        
        if week_id is not None:
            sentence_stack.append(f"week_id: {pc.CYAN}{week_id}{pc.RESET}")
        if sparse_Node2Node_edge_matrix is not None:
            sentence_stack.append(f"G Shape: {pc.CYAN}{sparse_Node2Node_edge_matrix.shape[0]} x {sparse_Node2Node_edge_matrix.shape[1]}{pc.RESET}")
            sentence_stack.append(f"NNZ: {pc.CYAN}{str(sparse_Node2Node_edge_matrix._nnz()).rjust(4)}{pc.RESET}")

        if procssing_ratio is not None:
            rounded_procssing_ratio = str(round(procssing_ratio*100, 2)).rjust(6)
            sentence_stack.append(f"Progress: {pc.CYAN}{rounded_procssing_ratio}%{pc.RESET}")

        print(
            *sentence_stack,
            end=end
        )

        return


    @staticmethod
    def display_note(note_title:str, content:Any):
        print(
            ' -',
            f"Title: [{pc.MAGENTA}{note_title}{pc.RESET}]: ",
            f"{content}"
        )

        return