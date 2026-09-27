"""ノード特徴量のカテゴリ/日付/目的変数の列定義と、カテゴリ変数 vocab の構築・保存・読込。

data_pipeline.py から分離。preprocess（vocab構築・feats格納）と graph_io（feats復元）の
両方から参照される、列レジストリと vocab ユーティリティをここに集約する。
"""

from __future__ import annotations

import json
import os
import re
from typing import Dict, List

import numpy as np
import pandas as pd

from scripts.datap.graph.cons import graph_params

# --------------------------------------------------------------------------
# カテゴリ変数・日付変数の列定義
# ここに列挙した列だけが「特殊扱い」（Embedding / Time2Vec 用）になり、
# それ以外の数値列はすべて連続値特徴量 x としてそのまま使われる。
# --------------------------------------------------------------------------
CATEGORICAL_COLUMNS: Dict[str, List[str]] = {
    "stock": ["S33", "S17", "Section_id", "Mkt", "Mrgn"],
    "statement": ["CurPerType"],
    "option": ["ProdCat", "UndSSO", "CM"],
    "future": ["ProdCat", "CM"],
}

DATE_COLUMNS: Dict[str, List[str]] = {
    "statement": ["CurFYEn"],
}

# --------------------------------------------------------------------------
# 目的変数（予測対象）の列定義。
# ここに列挙した列は cont（連続値特徴量 x）から必ず除外され、代わりに
# data[node_type][列名] として HeteroData に直接生やされる（is_target/time_id と同様）。
# "y" は翌週リターンが正かどうかの2値ラベル、"y_valid" はそのラベルが
# 定義可能か（系列末尾で翌週データが無い週は False）を示すマスク。
# --------------------------------------------------------------------------
LABEL_COLUMNS: Dict[str, List[str]] = {
    "stock": ["y", "y_valid"],
}

# 目的変数らしき列名（"y" 単体、または "y_" 始まり）が LABEL_COLUMNS への
# 登録漏れなどで誤って cont_cols に紛れ込んだ場合に検出するための安全弁。
# 新しい目的変数を追加する際は LABEL_COLUMNS にも必ず登録すること。
LABEL_LIKE_COLUMN_RE = re.compile(r"^y(_.*)?$", re.IGNORECASE)

DEFAULT_VOCAB_DIR = graph_params.DEFAULT_VOCAB_DIR

# Time2Vec など時間エンコーディングの基準日。
# この日からの経過日数(float)を生の時間スカラーとしてモデルに渡す。
# 値の定義は scripts/datap/graph/cons.py の graph_params に集約されている。
TIME_ENCODING_EPOCH = pd.Timestamp(graph_params.TIME_ENCODING_EPOCH)

# 浮動小数点特徴量の精度。numpy 側は FEATURE_FLOAT_DTYPE、
# HeteroData への tensor化時は TORCH_FLOAT_DTYPE を使う。
# 値の定義は scripts/datap/graph/cons.py の graph_params に集約されている。
FEATURE_FLOAT_DTYPE = graph_params.FEATURE_FLOAT_DTYPE
TORCH_FLOAT_DTYPE = graph_params.TORCH_FLOAT_DTYPE


def date_to_days_since_epoch(date_series: pd.Series) -> np.ndarray:
    """日付列を TIME_ENCODING_EPOCH からの経過日数(float)に変換する。

    ★ ここでは sin/cos 変換はしない。Time2Vec は周波数が学習パラメータ
    なので、前処理側では「生の時間スカラー」を渡すだけにするのが正しい。
    """
    ret = (pd.to_datetime(date_series) - TIME_ENCODING_EPOCH).dt.days.astype(FEATURE_FLOAT_DTYPE).values
    assert isinstance(ret, np.ndarray)
    return ret


def build_category_vocab(values) -> Dict[str, int]:
    """カテゴリ列のユニーク値から {値の文字列: 整数ID} の辞書を作る。

    末尾に "<UNK>" を追加しておくことで、vocab構築時に無かった値
    （例: train期間には存在しなかった業種区分がval/testに出現した場合）
    にも安全に対応できる。
    """
    unique_vals = sorted({str(v) for v in values})
    vocab = {v: i for i, v in enumerate(unique_vals)}
    vocab["<UNK>"] = len(vocab)
    return vocab


def encode_category(values, vocab: Dict[str, int]) -> np.ndarray:
    """カテゴリ列を vocab を使って整数IDの配列に変換する。"""
    unk = vocab["<UNK>"]
    return np.array([vocab.get(str(v), unk) for v in values], dtype=np.int64)


def vocab_path(vocab_dir: str, serial_id: int, node_type: str, column: str) -> str:
    return os.path.join(vocab_dir, f"vocab_{serial_id}_{node_type}_{column}.json")


def save_vocab(vocab: Dict[str, int], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(vocab, f, ensure_ascii=False, indent=2)


def load_vocab(path: str) -> Dict[str, int]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_vocab_sizes(serial_id: int, node_type: str, vocab_dir: str = DEFAULT_VOCAB_DIR) -> Dict[str, int]:
    """モデル側で nn.Embedding(num_embeddings=...) を構築する際に使う。
    例: get_vocab_sizes(1, "stock") -> {"S33": 34, "S17": 18, ...}
    """
    sizes = {}
    for col in CATEGORICAL_COLUMNS.get(node_type, []):
        vocab = load_vocab(vocab_path(vocab_dir, serial_id, node_type, col))
        sizes[col] = len(vocab)
    return sizes
