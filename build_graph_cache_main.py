"""グラフキャッシュ（HeteroData）だけを構築するスクリプト。model.baseline.model 等の
GNNモデル定義（torch_geometric.nn 経由）を一切importしない状態でパイプラインを
完走させることで、model/baseline/train.py 実行時に発生する不安定なネイティブ
クラッシュ（ACCESS_VIOLATION）を回避する。

背景: `model.baseline.model`（torch_geometric.nn.GraphConv/HeteroConv を使用）を
import した状態で scripts/datap/graph/data_pipeline.py の重い前処理
（CAPM相関計算・財務諸表の前処理など、pandas/duckdb/statsmodelsを多用する）を
同一プロセスで実行すると、タイミング依存でネイティブクラッシュする現象を確認した
（発生確率は高いが、決定論的に毎回同じ箇所で落ちるわけではない）。
一方、graphDataSet.process() が一度でも完走して
scripts/datap/graph/DS/processed/data_<serial_id>_full.pt が生成されていれば、
以降 train.py 側で graphDataSet を再構築しても process() は呼ばれず
（PyG の InMemoryDataset がキャッシュ済みファイルをロードするだけになる）、
危険なコードパス自体が実行されなくなる。

実行例:
    uv run python build_graph_cache_main.py --serial-id 9999
    uv run python -m model.baseline.train --serial-id 9999 --epochs 20
"""

from __future__ import annotations

import argparse
import os

from scripts.datap.graph.cons import rel_sql as cf
from scripts.datap.graph.data_pipeline import graphDataSet


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial-id", type=int, default=9999)
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "既存の graph_info_<serial_id>.duckdb を削除してから再構築する。"
            "前回の実行が異常終了して中途半端な状態のDBが残っている場合は必須"
            "（_ensure_db_built() はファイルの存在だけを見て再構築要否を判断するため）。"
        ),
    )
    args = parser.parse_args()

    db_path = cf.PATH_GRAPHINFO_DB.safe_substitute(serial_id=args.serial_id)
    if args.force and os.path.exists(db_path):
        os.remove(db_path)
        print(f"[build_graph_cache] removed stale {db_path}")

    print(f"[build_graph_cache] building graph cache for serial_id={args.serial_id} ...")
    dataset = graphDataSet(root="scripts/datap/graph/DS", serial_id=args.serial_id)
    data = dataset[0]
    print(f"[build_graph_cache] done. cached HeteroData: {data}")
    print(
        f"[build_graph_cache] processed file: "
        f"{os.path.join('scripts/datap/graph/DS/processed', dataset.processed_file_names[0])}"
    )


if __name__ == "__main__":
    main()
