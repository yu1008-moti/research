"""graph_info DB（fetch.*）と HeteroData の間を橋渡しする、ノード/エッジの取得・変換処理。

data_pipeline.py から分離。DB から返る node_id/feats 文字列・JSON を、
graphDataSet が HeteroData に詰め込める numpy 配列（cont/cat/date/label + 整数インデックス化
されたエッジ）へと変換するのがここの役割。
"""

from __future__ import annotations

import json
from typing import Dict, List, Tuple, TypedDict, cast

import numpy as np
import pandas as pd

from scripts.datap.graph.feature_encoding import (
    CATEGORICAL_COLUMNS,
    DATE_COLUMNS,
    FEATURE_FLOAT_DTYPE,
    LABEL_COLUMNS,
)
from scripts.datap.graph.sql import fetch


def fetch_edge_index(serial_id: int) -> Tuple[pd.arrays.ArrowStringArray, pd.arrays.ArrowStringArray]:
    """エッジ情報をデータベースから取得する。

    戻り値は (src_node_id, dst_node_id) の2つの (E,) 文字列配列。
    例: (['stock_11_1301', ...], ['stock_12_1301', ...])

    ★ 重要: ここで返る中身は "stock_12_1301" のような文字列の node_id であり、
    まだ整数インデックスではない。torch.tensor化する前に、必ず
    build_node_id_to_idx() で作った辞書を通して map_edge_ids_to_idx() で
    整数化すること。
    """
    df = fetch.edge_index(serial_id)  # 列: src_node_id, dst_node_id を想定
    src = df["src_node_id"].values.astype(str)
    dst = df["dst_node_id"].values.astype(str)

    assert isinstance(src, pd.arrays.ArrowStringArray)
    assert isinstance(dst, pd.arrays.ArrowStringArray)

    return src, dst


def fetch_edge_attr(serial_id: int, attr_name: str) -> np.ndarray:
    """エッジの属性情報をデータベースから取得する。(E,) の numpy 配列を返す。"""
    return fetch.edge_attr(serial_id, attr_name=attr_name).values.transpose().flatten()


class NodeFeatsPayload(TypedDict):
    """graph_node.feats 列に保存している JSON の構造。

    json.loads() の戻り値は本来 Any であり型チェッカーが中身を追えないため、
    parse_feats_json() でここに cast し、以降は辞書アクセスに型が付くようにする。
    """
    cont: Dict[str, float]
    cat: Dict[str, int]
    date: Dict[str, float]
    label: Dict[str, float]


def parse_feats_json(raw: str) -> NodeFeatsPayload:
    """feats列のJSON文字列をパースし、NodeFeatsPayload型として扱えるようにする。"""
    return cast(NodeFeatsPayload, json.loads(raw))


def extract_cont(payload: NodeFeatsPayload) -> List[float]:
    return list(payload["cont"].values())


def extract_cat(payload: NodeFeatsPayload, cat_cols: List[str]) -> List[int]:
    return [payload["cat"][c] for c in cat_cols]


def extract_date(payload: NodeFeatsPayload, date_cols: List[str]) -> List[float]:
    return [payload["date"][c] for c in date_cols]


def extract_label(payload: NodeFeatsPayload, label_cols: List[str]) -> List[float]:
    return [payload["label"][c] for c in label_cols]


def fetch_node_table(serial_id: int, node_type: str) -> Dict[str, np.ndarray]:
    """指定した node_type の全ノードを取得する。

    node_id は "stock_12_1301" のような文字列で管理されているため、
    ここでは DB 側に整数インデックス（node_idx）が存在することを前提にしない。
    代わりに、node_id文字列でソートして「決定的な順序」を確定させ、
    その並び順（0, 1, 2, ...）がそのままローカル整数インデックスになる。

    feats列のJSON構造は {"cont": {...}, "cat": {...}, "date": {...}, "label": {...}} を想定
    （node_feats_define() が書き込む形式と対応させている）。label グループは
    LABEL_COLUMNS[node_type] に登録された目的変数（例: stock の y / y_valid）を
    cont とは完全に分離して保持する。

    ★ 実際の DB スキーマに合わせて調整してください。
    ここでは graph_node テーブルに次の列がある想定で書いています：
        - node_id    : 'stock_1_1301' のような文字列ID（一意）
        - is_target  : bool（損失計算・予測対象かどうか）
        - time_id    : int（週インデックス。時系列split用）
        - feats      : JSON文字列（cont/cat/date の3グループ）
    """
    df = fetch.node_table(serial_id, node_type=node_type)  # 要: fetch側に実装
    # node_id 文字列で決定的にソートし、この並び順を「ローカル整数インデックス」とする
    df = df.sort_values("node_id").reset_index(drop=True)

    parsed: pd.Series = df["feats"].map(parse_feats_json)

    # 連続値特徴量
    cont_feats = np.stack(parsed.map(extract_cont).to_list())

    # カテゴリ変数（列の順序は CATEGORICAL_COLUMNS[node_type] に固定する）
    cat_cols = CATEGORICAL_COLUMNS.get(node_type, [])
    if cat_cols:
        cat_feats = np.stack(parsed.map(lambda p: extract_cat(p, cat_cols)).to_list())
    else:
        cat_feats = np.zeros((len(df), 0), dtype=np.int64)

    # 日付特徴量（Time2Vec等に渡す生の時間スカラー）
    date_cols = DATE_COLUMNS.get(node_type, [])
    if date_cols:
        date_feats = np.stack(parsed.map(lambda p: extract_date(p, date_cols)).to_list())
    else:
        date_feats = np.zeros((len(df), 0), dtype=FEATURE_FLOAT_DTYPE)

    # 目的変数（例: stock の y / y_valid）。cont には絶対含めず、ここだけで完結させる。
    label_cols = LABEL_COLUMNS.get(node_type, [])
    if label_cols:
        label_feats = np.stack(parsed.map(lambda p: extract_label(p, label_cols)).to_list())
    else:
        label_feats = np.zeros((len(df), 0), dtype=FEATURE_FLOAT_DTYPE)

    return {
        "x": cont_feats.astype(FEATURE_FLOAT_DTYPE),
        "cat_x": cat_feats.astype(np.int64),
        "date_x": date_feats.astype(FEATURE_FLOAT_DTYPE),
        "label_x": label_feats.astype(FEATURE_FLOAT_DTYPE),
        "is_target": df["is_target"].to_numpy(dtype=bool),
        "time_id": df["time_id"].to_numpy(dtype=np.int64),
        "node_str_id": df["node_id"].to_numpy(dtype=str),
    }


def build_node_id_to_idx(node_str_id: np.ndarray) -> Dict[str, int]:
    """node_id文字列 -> ローカル整数インデックス の辞書を作る。

    fetch_node_table() が返す node_str_id は既に「その並び順が
    ローカルインデックスである」という契約になっているため、
    単純に enumerate すればよい。
    """
    return {node_id: idx for idx, node_id in enumerate(node_str_id)}


def map_edge_ids_to_idx(
    src_ids: pd.arrays.ArrowStringArray,
    dst_ids: pd.arrays.ArrowStringArray,
    src_map: Dict[str, int],
    dst_map: Dict[str, int],
) -> np.ndarray:
    """文字列の src/dst node_id 配列を、それぞれのノードタイプの
    整数インデックスに変換し、(2, E) の numpy 配列を返す。

    src_map に無い src_id / dst_map に無い dst_id が来た場合は例外を出す
    （サイレントに握りつぶすと、後段でノード数不一致などの気づきにくい
    バグにつながるため、ここで早期に検出する）。
    """
    try:
        src_idx = np.array([src_map[s] for s in src_ids], dtype=np.int64)
        dst_idx = np.array([dst_map[d] for d in dst_ids], dtype=np.int64)
    except KeyError as e:
        raise KeyError(
            f"edge が参照している node_id がノードテーブルに存在しません: {e}. "
            "ノード生成(node_id_define)とエッジ生成の対象範囲がズレている可能性があります。"
        ) from e
    return np.stack([src_idx, dst_idx], axis=0)
