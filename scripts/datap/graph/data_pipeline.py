"""グラフ構築パイプラインの公開エントリポイント（後方互換のための再エクスポート層）。

このファイルはかつて、ノード/エッジ登録・HeteroData組み立て・NeighborLoader設定を
すべて1000行超の単一モジュールとして持っていたが、把握しづらくなったため
以下のファイルに機能ごとに分割した。実装本体はそちらを参照すること:

- `feature_encoding.py` — カテゴリ/日付/目的変数の列レジストリと vocab 構築・保存・読込
- `graph_io.py`          — graph_info DB <-> HeteroData 用 numpy 配列 の変換（fetch/parse）
- `preprocess.py`        — raw データ(financials/prices/options/futures) -> graph_node/graph_edge
                           テーブルへの前処理（`preprocess` クラス）
- `dataset.py`           — 上記を束ねて単一の HeteroData を構築する PyG Dataset（`graphDataSet`）
- `loaders.py`           — train/val/test 用 NeighborLoader/HGTLoader 構築（`get_loaders`）

`from scripts.datap.graph.data_pipeline import ...` という既存の import パスを
壊さないよう、各ファイルの公開シンボルをここに再エクスポートしている。
新規コードは対象のファイルから直接importして構わない。
"""

from __future__ import annotations

from scripts.datap.graph.dataset import (
    REVERSE_RELATIONS,
    graphDataSet,
)
from scripts.datap.graph.feature_encoding import (
    CATEGORICAL_COLUMNS,
    DATE_COLUMNS,
    DEFAULT_VOCAB_DIR,
    FEATURE_FLOAT_DTYPE,
    LABEL_COLUMNS,
    TIME_ENCODING_EPOCH,
    TORCH_FLOAT_DTYPE,
    build_category_vocab,
    date_to_days_since_epoch,
    encode_category,
    get_vocab_sizes,
    load_vocab,
    save_vocab,
    vocab_path,
)
from scripts.datap.graph.graph_io import (
    NodeFeatsPayload,
    build_node_id_to_idx,
    fetch_edge_attr,
    fetch_edge_index,
    fetch_node_table,
    map_edge_ids_to_idx,
    parse_feats_json,
)
from scripts.datap.graph.loaders import get_loaders, mock_code
from scripts.datap.graph.preprocess import (
    MARKET_INDEX_FUTURE_PRODCATS,
    TARGET_STOCK_MKT_CODES,
    preprocess,
)

__all__ = [
    "REVERSE_RELATIONS",
    "graphDataSet",
    "CATEGORICAL_COLUMNS",
    "DATE_COLUMNS",
    "DEFAULT_VOCAB_DIR",
    "FEATURE_FLOAT_DTYPE",
    "LABEL_COLUMNS",
    "TIME_ENCODING_EPOCH",
    "TORCH_FLOAT_DTYPE",
    "build_category_vocab",
    "date_to_days_since_epoch",
    "encode_category",
    "get_vocab_sizes",
    "load_vocab",
    "save_vocab",
    "vocab_path",
    "NodeFeatsPayload",
    "build_node_id_to_idx",
    "fetch_edge_attr",
    "fetch_edge_index",
    "fetch_node_table",
    "map_edge_ids_to_idx",
    "parse_feats_json",
    "get_loaders",
    "mock_code",
    "MARKET_INDEX_FUTURE_PRODCATS",
    "TARGET_STOCK_MKT_CODES",
    "preprocess",
]
