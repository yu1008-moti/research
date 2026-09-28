"""単一の HeteroData から train/val/test 用の近傍サンプリング Loader を構築する。

data_pipeline.py から分離。`graphDataSet` をロードし、time_id ベースで
train/val/test マスクを作った上で NeighborLoader / HGTLoader を組み立てる。
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import torch
from torch_geometric.data import HeteroData
from torch_geometric.loader import HGTLoader, NeighborLoader

from scripts.datap.graph.cons import graph_params
from scripts.datap.graph.dataset import graphDataSet


def get_loaders(
    serial_id: int = 1,
    split_1_per: float = graph_params.SPLIT_1_PER,
    split_2_per: float = graph_params.SPLIT_2_PER,
    batch_size: int = graph_params.BATCH_SIZE,
    num_neighbors: Dict[Tuple[str, str, str], List[int]] | None = None,
    sampler: str = graph_params.SAMPLER,
    num_samples: Dict[str, List[int]] | List[int] | None = None,
    num_neighbors_per_hop: int = graph_params.NUM_NEIGHBORS_PER_HOP,
    num_hops: int = graph_params.NUM_HOPS,
    num_workers: int = graph_params.NUM_WORKERS,
):
    """train/val/test 用の近傍サンプリング Loader を1つの単一グラフから構築する。

    - グラフ自体は分割しない（過去情報へのアクセスを維持するため）。
    - is_target かつ y_valid（翌週リターンが定義できる週。系列末尾は False）かつ
      time_id が各期間に属する stock ノードだけを input_nodes（＝バッチ生成の
      起点かつ損失計算対象）とする。y_valid=False のノードはラベルが意味的に
      不定（y=0 に落ちているだけ）なので、常に学習・評価対象から除外する。

    sampler:
        'neighbor'（既定, torch_geometric.loader.NeighborLoader）:
            num_neighbors（エッジタイプごとの1ホップあたり近傍数）を使う。
            明示指定が無ければ num_neighbors_per_hop を num_hops ホップ分、
            全エッジ種別に一律適用する。
        'hgt'（torch_geometric.loader.HGTLoader, HGT論文 [Hu+ 2020] の HGSampling）:
            ※ 実行環境に torch-sparse が必要（本プロジェクトの環境では未導入・
            対応wheel無しのため現状未検証。導入するとネイティブ拡張が増え、
            過去に発生したネイティブクラッシュと同種のリスクを伴う点に注意）。
            num_samples（ノードタイプごとの1ホップあたりサンプル数）を使う。
            ノードタイプ単位で独立した予算を持ち、次数で正規化した重要度で
            サンプリングするため、'neighbor' がエッジタイプに一律の近傍数を
            課すことで生じる、密なタイプ（例: option）への計算コストの偏りを
            緩和できる可能性がある。

    num_neighbors_per_hop, num_hops:
        num_neighbors / num_samples を明示指定しない場合に使われる、全タイプ一律の
        「1ホップあたりサンプル数」と「ホップ数」。ホップ数を増減させると
        サンプリングされるサブグラフのサイズ（＝1バッチあたりの計算コスト）が
        指数的に変化するため、学習時間を左右する最も影響の大きいパラメータ。
        train.py の --num-neighbors-per-hop / --num-hops で上書き可能。

    num_workers:
        NeighborLoader/HGTLoader のバックグラウンドワーカープロセス数。既定は
        graph_params.NUM_WORKERS（=0、メインプロセスのみ）。0より大きい値を渡す
        場合、呼び出し元は必ず `if __name__ == "__main__":` 配下で get_loaders()
        を呼ぶこと（Windows の multiprocessing は spawn 方式のため、ガードが
        無いと各ワーカープロセスがモジュールのトップレベルコードを再実行して
        しまう。repo root の test_temp.py はガード無しでこの関数を呼んでいるため
        特に注意）。0より大きい場合のみ persistent_workers=True・
        prefetch_factor=4 を内部で付与する（PyTorchは num_workers=0 に対して
        これらの引数を渡すとエラーになるため）。train.py の --num-workers で
        上書き可能。
    """
    dataset = graphDataSet(root="scripts/datap/graph/DS", serial_id=serial_id)
    data = dataset[0]

    assert isinstance(data, HeteroData)

    time_id = data["stock"].time_id
    is_target = data["stock"].is_target
    y_valid = data["stock"].y_valid.bool()

    t_min, t_max = time_id.min().item(), time_id.max().item()
    split_1 = t_min + split_1_per * (t_max - t_min)
    split_2 = t_min + split_2_per * (t_max - t_min)

    train_mask = is_target & y_valid & (time_id < split_1)
    val_mask = is_target & y_valid & (time_id >= split_1) & (time_id < split_2)
    test_mask = is_target & y_valid & (time_id >= split_2)

    # num_workers=0 に persistent_workers/prefetch_factor を渡すと PyTorch が
    # ValueError を出すため、0より大きい場合のみ付与する（**kwargs 展開だと
    # NeighborLoader/HGTLoader 側の厳密な引数型と噛み合わず型チェッカーが
    # 誤検知するため、if分岐で明示的に呼び分ける）。
    if sampler == "neighbor":
        if num_neighbors is None:
            # 明示指定が無ければ、グラフに実在する全エッジ種別に対して
            # num_neighbors_per_hop を num_hops ホップ分一律に適用する。
            # エッジ種別ごとに差を付けたい場合は、この関数の num_neighbors 引数に
            # 辞書を渡して上書きすればよい
            # （例: hub化しやすい ("future","rev_derivative","stock") だけ小さくする等）。
            per_hop = [num_neighbors_per_hop] * num_hops
            num_neighbors = {edge_type: per_hop for edge_type in data.edge_types}

        def _make_loader(mask: torch.Tensor, shuffle: bool) -> NeighborLoader | HGTLoader:
            if num_workers > 0:
                return NeighborLoader(
                    data,
                    num_neighbors=num_neighbors,
                    input_nodes=("stock", mask),
                    batch_size=batch_size,
                    shuffle=shuffle,
                    num_workers=num_workers,
                    persistent_workers=True,
                    prefetch_factor=4,
                )
            return NeighborLoader(
                data,
                num_neighbors=num_neighbors,
                input_nodes=("stock", mask),
                batch_size=batch_size,
                shuffle=shuffle,
            )

    elif sampler == "hgt":
        if num_samples is None:
            # 明示指定が無ければ、グラフに実在する全ノードタイプに対して
            # graph_params.NUM_SAMPLES_PER_HOP を num_hops ホップ分一律に適用する。
            # ノードタイプごとに差を付けたい場合は、この関数の num_samples 引数に
            # 辞書を渡して上書きすればよい（例: 母数・次数が大きい "option" だけ
            # 小さくする等）。
            per_hop = [graph_params.NUM_SAMPLES_PER_HOP] * num_hops
            num_samples = {node_type: per_hop for node_type in data.node_types}

        def _make_loader(mask: torch.Tensor, shuffle: bool) -> NeighborLoader | HGTLoader:
            if num_workers > 0:
                return HGTLoader(
                    data,
                    num_samples=num_samples,
                    input_nodes=("stock", mask),
                    batch_size=batch_size,
                    shuffle=shuffle,
                    num_workers=num_workers,
                    persistent_workers=True,
                    prefetch_factor=4,
                )
            return HGTLoader(
                data,
                num_samples=num_samples,
                input_nodes=("stock", mask),
                batch_size=batch_size,
                shuffle=shuffle,
            )

    else:
        raise ValueError(f"unknown sampler: {sampler!r} (expected 'neighbor' or 'hgt')")

    train_loader = _make_loader(train_mask, shuffle=True)
    val_loader = _make_loader(val_mask, shuffle=False)
    test_loader = _make_loader(test_mask, shuffle=False)

    return train_loader, val_loader, test_loader