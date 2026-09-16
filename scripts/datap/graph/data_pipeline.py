from __future__ import annotations

import json
import os
import re
from datetime import datetime as dt
from typing import Dict, List, Tuple, TypedDict, cast
import importlib

import duckdb as db
import numpy as np
import pandas as pd
import torch
from torch_geometric.data import HeteroData, InMemoryDataset
from torch_geometric.loader import HGTLoader, NeighborLoader

from scripts.datap.graph import capm_corr, derivative_corr
from scripts.datap.graph.cons import graph_params, rel_sql as cf
from scripts.datap.graph.sql import create, fetch, insert

# --------------------------------------------------------------------------
# 逆エッジを自動生成したい関係。
# {(src, rel, dst): 逆方向の relation 名}
# 対称な関係（相関エッジなど）はここに入れない。
# --------------------------------------------------------------------------
REVERSE_RELATIONS: Dict[Tuple[str, str, str], str] = {
    ("statement", "report", "stock"): "rev_report",
    ("stock", "derivative", "option"): "rev_derivative",
    ("stock", "derivative", "future"): "rev_derivative",
}

# --------------------------------------------------------------------------
# Stock__derivative__Future で全対象銘柄を接続する「主要な株価指数先物」の商品区分。
# 先物は個別株の原資産を持たない（指数・債券・通貨先物のみ）ため、
# 市場全体のシステマティックリスクを媒介する backbone として、この区分の期近物
# （SQRemainingDays が最小の契約）に全 is_target 銘柄を一律接続する。
# 値の定義は scripts/datap/graph/cons.py の graph_params に集約されている。
# --------------------------------------------------------------------------
MARKET_INDEX_FUTURE_PRODCATS: List[str] = graph_params.MARKET_INDEX_FUTURE_PRODCATS

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
_LABEL_LIKE_COLUMN_RE = re.compile(r"^y(_.*)?$", re.IGNORECASE)

DEFAULT_VOCAB_DIR = graph_params.DEFAULT_VOCAB_DIR

_SAFE_GLOBALS_REGISTERED = False


def _allow_numpy_globals_for_torch_load() -> None:
    """torch.load(weights_only=True) が HeteroData 内の numpy 配列
    (node_str_id など文字列配列) を復元できるよう、安全なグローバル関数として
    許可リストに登録する。

    ★ ここで許可しているのは「自分自身の前処理が書き出した.ptファイルの復元に
    必要な、numpyの内部関数」のみ。他者から受け取った信頼できないファイルの
    読み込みにこの安全性を流用しないこと。
    """
    global _SAFE_GLOBALS_REGISTERED
    if _SAFE_GLOBALS_REGISTERED:
        return

    # np.core.multiarray / np._core.multiarray への直接の属性アクセスは
    # numpyの型スタブが公開していないため Pylance が誤検知する。
    # importlib + getattr(文字列) による動的アクセスに統一して回避する。
    module_name = "numpy._core.multiarray" if hasattr(np, "_core") else "numpy.core.multiarray"
    multiarray_module = importlib.import_module(module_name)
    reconstruct = getattr(multiarray_module, "_reconstruct")

    torch.serialization.add_safe_globals([reconstruct, np.ndarray, np.dtype])
    _SAFE_GLOBALS_REGISTERED = True

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


class preprocess:
    """データを前処理し、graph_node および graph_edge テーブルに格納する。"""

    def __init__(self, financials_df: pd.DataFrame, prices_df: pd.DataFrame,
                 options_df: pd.DataFrame, futures_df: pd.DataFrame, serial_id: int = 1,
                 vocab_dir: str = DEFAULT_VOCAB_DIR):
        self.financials_df = financials_df
        self.prices_df = prices_df
        self.options_df = options_df
        self.futures_df = futures_df
        self.serial_id = serial_id
        self.vocab_dir = vocab_dir
        self.unique_week_id = sorted(
            set(financials_df["week_id"].unique())
            .union(set(prices_df["week_id"].unique()))
            .union(set(options_df["week_id"].unique()))
            .union(set(futures_df["week_id"].unique()))
        )

    @property
    def get_unique_week_id(self) -> List[int]:
        return self.unique_week_id

    # ------------------------------------------------------------------
    # 1. graph_edge に関する処理
    # ------------------------------------------------------------------
    def stock_corr_stock_preprocess(self):
        """銘柄間 CAPM 残差相関エッジを計算し、graph_edge テーブルに格納する。

        ★ データ不整合対応
        capm_corr.build_firm_corr_edges() は固定の銘柄ユニバース(firm_id_order)
        を前提に相関を計算しており、ある銘柄がまだ上場していない週についても
        エッジを生成してしまうことがある（例: 2024年新規上場の '130A0' が
        2015年時点のエッジに登場する、等）。node_id_define() は実際に価格データが
        存在する (week, code) からしか stock ノードを作らないため、
        そのままだと存在しないノードを指すダングリングエッジになる。
        したがって、report エッジと同様に「実在する (week, code) にのみ
        エッジを張る」フィルタをここでも適用する。
        """
        prices_df = self.prices_df.copy()
        prices_df["week_id"] = prices_df["week_id"].astype(int)
        valid_pairs = set(zip(prices_df["week_id"], prices_df["Code"]))

        src, dst = 0, 1

        firm_corr = capm_corr.build_firm_corr_edges(prices_df)
        firm_id_order = firm_corr.firm_id_order

        n_dropped = 0
        n_kept = 0
        for week_id, (edge_index, edge_weight) in sorted(firm_corr.edges.items()):
            week_id_int = int(week_id)

            src_tk = [firm_id_order[i - 1] for i in edge_index[src].cpu().numpy()]
            dst_tk = [firm_id_order[i - 1] for i in edge_index[dst].cpu().numpy()]
            weight_list = edge_weight.cpu().numpy().tolist()

            # 実在する (week, code) の組み合わせにのみ絞り込む
            keep_mask = [
                (week_id_int, s) in valid_pairs and (week_id_int, d) in valid_pairs
                for s, d in zip(src_tk, dst_tk)
            ]
            n_dropped += len(keep_mask) - sum(keep_mask)
            n_kept += sum(keep_mask)

            src_tk_f = [s for s, keep in zip(src_tk, keep_mask) if keep]
            dst_tk_f = [d for d, keep in zip(dst_tk, keep_mask) if keep]
            weight_f = [w for w, keep in zip(weight_list, keep_mask) if keep]

            if not src_tk_f:
                continue

            week_id_str = str(week_id_int)
            src_node_id = [f"stock_{week_id_str}_{code}" for code in src_tk_f]
            dst_node_id = [f"stock_{week_id_str}_{code}" for code in dst_tk_f]
            edge_id = [f"stock__corr__stock_{week_id_str}_{s}_{d}" for s, d in zip(src_tk_f, dst_tk_f)]

            insert.edge(pd.DataFrame({
                "edge_id": edge_id,
                # "__" 区切りで (src_type, relation, dst_type) を一意にパースできるようにする
                "edge_type": ["stock__corr__stock"] * len(src_tk_f),
                "src_node_id": src_node_id,
                "dst_node_id": dst_node_id,
                "edge_weight_list": weight_f,
                "observable_time_id": [week_id_int] * len(src_tk_f),
            }), self.serial_id)

        print(
            f"[stock_corr_stock] 対応する株価ノードが無いため "
            f"{n_dropped}件の相関エッジをスキップ（採用: {n_kept}件）"
        )

        # 同一銘柄の 1-step 前 -> 現時点 のエッジ（相関と同じ node type なので同じ relation にまとめる）
        for code in prices_df["Code"].unique():
            code_df = prices_df[prices_df["Code"] == code].copy()

            src_week = code_df["week_id"].shift(1).values[1:].astype(int).astype(str)
            dst_week = code_df["week_id"].values[1:].astype(int).astype(str)

            src_node_id = [f"stock_{w}_{code}" for w in src_week]
            dst_node_id = [f"stock_{w}_{code}" for w in dst_week]
            edge_id = [f"stock__corr__stock_{w}_{code}_{code}" for w in dst_week]

            insert.edge(pd.DataFrame({
                "edge_id": edge_id,
                "edge_type": ["stock__corr__stock"] * len(src_node_id),
                "src_node_id": src_node_id,
                "dst_node_id": dst_node_id,
                "edge_weight_list": [1.0] * len(src_node_id),
                "observable_time_id": [int(w) for w in dst_week],
            }), self.serial_id)

    def _insert_peer_corr_edges(self, peer_corr: derivative_corr.PeerCorrEdges, node_type: str) -> None:
        """derivative_corr.build_peer_corr_edges() の結果を graph_edge テーブルに書き込む共通処理。"""
        edge_type = f"{node_type}__corr__{node_type}"

        for week_id, week_edges in sorted(peer_corr.edges.items()):
            if not week_edges:
                continue

            src_codes = [e[0] for e in week_edges]
            dst_codes = [e[1] for e in week_edges]
            weights = [e[2] for e in week_edges]

            week_id_str = str(week_id)
            src_node_id = [f"{node_type}_{week_id_str}_{c}" for c in src_codes]
            dst_node_id = [f"{node_type}_{week_id_str}_{c}" for c in dst_codes]
            edge_id = [f"{edge_type}_{week_id_str}_{s}_{d}" for s, d in zip(src_codes, dst_codes)]

            insert.edge(pd.DataFrame({
                "edge_id": edge_id,
                "edge_type": [edge_type] * len(src_codes),
                "src_node_id": src_node_id,
                "dst_node_id": dst_node_id,
                "edge_weight_list": weights,
                "observable_time_id": [week_id] * len(src_codes),
            }), self.serial_id)

    def option_corr_option_preprocess(self):
        """同一原資産(UndSSO)を持つオプション契約同士の相関エッジを作成する。

        原資産が無い（＝UndSSOがNULL）指数・債券オプションはグループ化できないため対象外。
        """
        options_df = self.options_df.copy()
        options_df["week_id"] = options_df["week_id"].astype(int)

        peer_corr = derivative_corr.build_peer_corr_edges(
            options_df, group_col="UndSSO", code_col="Code", close_col="AdjC",
        )
        self._insert_peer_corr_edges(peer_corr, node_type="option")

    def future_corr_future_preprocess(self):
        """同一商品区分(ProdCat)を持つ先物契約同士の相関エッジを作成する。"""
        futures_df = self.futures_df.copy()
        futures_df["week_id"] = futures_df["week_id"].astype(int)

        peer_corr = derivative_corr.build_peer_corr_edges(
            futures_df, group_col="ProdCat", code_col="Code", close_col="AdjC",
        )
        self._insert_peer_corr_edges(peer_corr, node_type="future")

    def _prev_chain_preprocess(self, df: pd.DataFrame, node_type: str) -> None:
        """同一契約(Code)の時系列エッジ（前週 -> 今週）を作成する共通処理。

        statement_prev_statement_preprocess と同じ意味合い（同一契約の週を跨いだ
        連結）だが、オプションは（限られた週範囲でも）数万契約に達するため、
        statement/stock 側のようなコード単位の Python ループ + 逐次 insert では
        実用的な時間で終わらない（実測: 20週分・約3万契約で約30分）。
        そのため groupby + shift による一括ベクトル化と、1回のバルク insert で処理する。
        """
        df = df[["week_id", "Code"]].copy()
        df["week_id"] = df["week_id"].astype(int)
        df = df.sort_values(["Code", "week_id"])
        edge_type = f"{node_type}__prev__{node_type}"

        df["_prev_week_id"] = df.groupby("Code")["week_id"].shift(1)
        chained = df.dropna(subset=["_prev_week_id"])
        print(f"[{node_type}_prev_{node_type}] {len(chained)}件の prev エッジを作成します")

        if chained.empty:
            return

        src_week = chained["_prev_week_id"].astype(int).astype(str).to_numpy()
        dst_week = chained["week_id"].astype(str).to_numpy()
        codes = chained["Code"].to_numpy()

        src_node_id = [f"{node_type}_{w}_{c}" for w, c in zip(src_week, codes)]
        dst_node_id = [f"{node_type}_{w}_{c}" for w, c in zip(dst_week, codes)]
        edge_id = [f"{edge_type}_{w}_{c}_{c}" for w, c in zip(dst_week, codes)]

        insert.edge(pd.DataFrame({
            "edge_id": edge_id,
            "edge_type": [edge_type] * len(src_node_id),
            "src_node_id": src_node_id,
            "dst_node_id": dst_node_id,
            "edge_weight_list": [1.0] * len(src_node_id),
            "observable_time_id": [int(w) for w in dst_week],
        }), self.serial_id)

    def option_prev_option_preprocess(self):
        """同一オプション契約の時系列エッジ（前週 -> 今週）を作成する。"""
        self._prev_chain_preprocess(self.options_df, node_type="option")

    def future_prev_future_preprocess(self):
        """同一先物契約の時系列エッジ（前週 -> 今週）を作成する。"""
        self._prev_chain_preprocess(self.futures_df, node_type="future")

    def stock_derivative_option_preprocess(self):
        """銘柄ノード -> その原資産とするオプション契約ノード への派生エッジを作成する。

        ★ データ不整合対応
        UndSSO が NULL（指数・債券オプション）の行は原資産の個別株が存在しないため対象外。
        また report エッジと同様、株価データが実在する (week, code) にのみエッジを張る。
        """
        options_df = self.options_df.copy()
        options_df["week_id"] = options_df["week_id"].astype(int)
        options_df = options_df.dropna(subset=["UndSSO"])

        prices_df = self.prices_df.copy()
        prices_df["week_id"] = prices_df["week_id"].astype(int)
        valid_pairs = prices_df[["week_id", "Code"]].drop_duplicates()

        merged = options_df.merge(
            valid_pairs, left_on=["week_id", "UndSSO"], right_on=["week_id", "Code"],
            how="inner", suffixes=("", "_stock"),
        )

        n_dropped = len(options_df) - len(merged)
        print(
            f"[stock_derivative_option] 対応する株価データが無いため "
            f"{n_dropped}件の derivative エッジをスキップ"
        )

        if merged.empty:
            return

        week = merged["week_id"].values.astype(str)
        stock_code = merged["UndSSO"].values
        option_code = merged["Code"].values

        src_node_id = [f"stock_{w}_{c}" for w, c in zip(week, stock_code)]
        dst_node_id = [f"option_{w}_{c}" for w, c in zip(week, option_code)]
        edge_id = [
            f"stock__derivative__option_{w}_{sc}_{oc}"
            for w, sc, oc in zip(week, stock_code, option_code)
        ]

        insert.edge(pd.DataFrame({
            "edge_id": edge_id,
            "edge_type": ["stock__derivative__option"] * len(src_node_id),
            "src_node_id": src_node_id,
            "dst_node_id": dst_node_id,
            "edge_weight_list": [1.0] * len(src_node_id),
            "observable_time_id": [int(w) for w in week],
        }), self.serial_id)

    def stock_derivative_future_preprocess(self):
        """全 is_target 銘柄ノード -> 主要な株価指数先物（期近物）ノード への派生エッジを作成する。

        先物は個別株の原資産を持たない（指数・債券・通貨先物のみ）ため、
        MARKET_INDEX_FUTURE_PRODCATS で指定した株価指数先物の期近物（SQRemainingDaysが
        最小の契約）に、その週の全対象銘柄を一律接続する "market backbone" 構造とする。
        """
        futures_df = self.futures_df.copy()
        futures_df["week_id"] = futures_df["week_id"].astype(int)

        candidates = futures_df[futures_df["ProdCat"].isin(MARKET_INDEX_FUTURE_PRODCATS)].copy()
        if candidates.empty:
            print(
                "[stock_derivative_future] MARKET_INDEX_FUTURE_PRODCATS に該当する"
                "先物データがありません"
            )
            return

        # 期近物（SQRemainingDaysが非負で最小）を週・商品区分ごとに選ぶ。
        # 全て負（＝期限切れ扱い）の場合はそのうち最大値（最も期限切れが浅いもの）を採用する。
        candidates["_is_not_expired"] = candidates["SQRemainingDays"] >= 0
        candidates = candidates.sort_values(
            ["week_id", "ProdCat", "_is_not_expired", "SQRemainingDays"],
            ascending=[True, True, False, True],
        )
        front_month = candidates.groupby(["week_id", "ProdCat"], as_index=False).first()

        prices_df = self.prices_df.copy()
        prices_df["week_id"] = prices_df["week_id"].astype(int)
        target_stocks = prices_df[
            (prices_df["Mkt"] == "0000") | (prices_df["Mkt"] == "0500")
        ][["week_id", "Code"]].drop_duplicates()

        merged = target_stocks.merge(
            front_month[["week_id", "Code", "ProdCat"]], on="week_id", suffixes=("", "_future"),
        )

        if merged.empty:
            return

        week = merged["week_id"].values.astype(str)
        stock_code = merged["Code"].values
        future_code = merged["Code_future"].values

        src_node_id = [f"stock_{w}_{c}" for w, c in zip(week, stock_code)]
        dst_node_id = [f"future_{w}_{c}" for w, c in zip(week, future_code)]
        edge_id = [
            f"stock__derivative__future_{w}_{sc}_{fc}"
            for w, sc, fc in zip(week, stock_code, future_code)
        ]

        insert.edge(pd.DataFrame({
            "edge_id": edge_id,
            "edge_type": ["stock__derivative__future"] * len(src_node_id),
            "src_node_id": src_node_id,
            "dst_node_id": dst_node_id,
            "edge_weight_list": [1.0] * len(src_node_id),
            "observable_time_id": [int(w) for w in week],
        }), self.serial_id)

    def statement_prev_statement_preprocess(self):
        """決算ノードの時系列エッジ（前期 -> 今期）を作成する。"""
        financials_df = self.financials_df.copy()
        codes = financials_df["Code"].unique()

        for i, code in enumerate(codes, start=1):
            print(f"\rProcessing code: {code} ({i}/{len(codes)})", end=" ")
            code_df = financials_df[financials_df["Code"] == code].copy()

            src_week = code_df["week_id"].shift(1).values[1:].astype(int).astype(str)
            dst_week = code_df["week_id"].values[1:].astype(int).astype(str)

            src_node_id = [f"statement_{w}_{code}" for w in src_week]
            dst_node_id = [f"statement_{w}_{code}" for w in dst_week]
            edge_id = [f"statement__prev__statement_{w}_{code}_{code}" for w in dst_week]

            insert.edge(pd.DataFrame({
                "edge_id": edge_id,
                "edge_type": ["statement__prev__statement"] * len(src_node_id),
                "src_node_id": src_node_id,
                "dst_node_id": dst_node_id,
                "edge_weight_list": [1.0] * len(src_node_id),
                "observable_time_id": [int(w) for w in dst_week],
            }), self.serial_id)
        print()

    def statement_report_stock_preprocess(self):
        """決算ノード -> 銘柄ノード への報告エッジを作成する。
        (旧: stock_report_statement_preprocess。関数名と方向の矛盾を解消して改名)

        ★ データ不整合対応（2013/07/16 東証・大証統合、名証→東証の個別上場替え等）
        決算発表履歴はあるが対応する株価データが存在しない (week, code) の組が
        1214銘柄で発生している（大証専売銘柄の統合前データ・他市場からの
        上場替え銘柄など）。この場合 stock ノード自体が存在しないため、
        report エッジを作るとダングリングエッジ（存在しないノードを指す
        エッジ）になってしまう。

        固定の日付（2013/07/16）で一律に区切ると、上場替えの時期が銘柄ごとに
        異なる122銘柄（例: 5356, 5461）には対応できない。そのため、
        「株価データが実在する (week, code) にのみエッジを張る」という
        汎用的な存在チェックに一般化して対応する。

        決算データ自体は削除しない。report エッジが無い期間の statement ノード
        は孤立するが、statement__prev__statement のチェーンを通じて、
        株価と接続される時点以降の statement ノードから多ホップで
        参照可能なままなので、情報は失われない。
        """
        financials_df = self.financials_df.copy()
        financials_df["week_id"] = financials_df["week_id"].astype(int)

        prices_df = self.prices_df.copy()
        prices_df["week_id"] = prices_df["week_id"].astype(int)

        # 実在する (week_id, Code) の組だけを対象にする（inner join）
        valid_pairs = prices_df[["week_id", "Code"]].drop_duplicates()
        merged = financials_df.merge(valid_pairs, on=["week_id", "Code"], how="inner")

        n_dropped = len(financials_df) - len(merged)
        n_codes_dropped = financials_df["Code"].nunique() - merged["Code"].nunique()
        print(
            f"[statement_report_stock] 対応する株価データが無いため "
            f"{n_dropped}件のreportエッジをスキップ（影響銘柄: 最大{n_codes_dropped}件）"
        )

        if merged.empty:
            return

        week = merged["week_id"].values.astype(str)
        code = merged["Code"].values

        src_node_id = [f"statement_{w}_{c}" for w, c in zip(week, code)]  # src = statement
        dst_node_id = [f"stock_{w}_{c}" for w, c in zip(week, code)]      # dst = stock
        edge_id = [f"statement__report__stock_{w}_{c}_{c}" for w, c in zip(week, code)]

        insert.edge(pd.DataFrame({
            "edge_id": edge_id,
            "edge_type": ["statement__report__stock"] * len(src_node_id),
            "src_node_id": src_node_id,
            "dst_node_id": dst_node_id,
            "edge_weight_list": [1.0] * len(src_node_id),
            "observable_time_id": [int(w) for w in week],
            }), self.serial_id)

    # ------------------------------------------------------------------
    # 2. graph_node に関する処理
    # ------------------------------------------------------------------
    def node_id_define(self):
        """銘柄・決算・オプション・先物ノードの node_id / is_target / time_id を定義する。"""
        using_df_list = [
            (self.financials_df.copy(), "statement"),
            (self.prices_df.copy(), "stock"),
            (self.options_df.copy(), "option"),
            (self.futures_df.copy(), "future"),
        ]

        for i, (df, node_type) in enumerate(using_df_list, start=1):
            print(f"Processing node_type: {node_type} ({i}/{len(using_df_list)})")

            node_id = df.apply(lambda row: f'{node_type}_{int(row["week_id"])}_{row["Code"]}', axis=1)
            tickers = df["Code"].values

            if node_type == "stock":
                is_target = ((df["Mkt"] == "0000") | (df["Mkt"] == "0500")).astype(bool).tolist()
            else:
                is_target = [False] * len(df)

            insert.node(pd.DataFrame({
                "node_id": node_id,
                "is_target": is_target,
                "ticker": tickers,
                "node_type": [node_type] * len(df),
                "time_id": df["week_id"].values.astype(int),
            }), self.serial_id)

    # ------------------------------------------------------------------
    # 3. カテゴリ変数の vocab 構築
    # ------------------------------------------------------------------
    def build_category_vocabs(self):
        """カテゴリ列ごとに {値: 整数ID} の vocab を作り、ディスクに保存する。

        ★ ここでは train/val/test を分けずに全期間のデータから vocab を作る。
        これは「未来の株価やラベルを覗き見ている」わけではなく、単に
        「業種区分・市場区分としてどんな値が存在し得るか」という
        カテゴリの世界観を定義しているだけなので、リークとは区別される。
        （新しい業種が将来追加される可能性に備えて <UNK> 枠を用意している）
        """
        using_df_list = [
            (self.financials_df, "statement"),
            (self.prices_df, "stock"),
            (self.options_df, "option"),
            (self.futures_df, "future"),
        ]
        for df, node_type in using_df_list:
            for col in CATEGORICAL_COLUMNS.get(node_type, []):
                vocab = build_category_vocab(df[col].values)
                save_vocab(vocab, vocab_path(self.vocab_dir, self.serial_id, node_type, col))
                print(f"[vocab] {node_type}.{col}: {len(vocab)} categories (UNK含む)")

    # ------------------------------------------------------------------
    # 4. node_feats に関する処理
    # ------------------------------------------------------------------
    def node_feats_define(self):
        """銘柄ノード・決算ノードの特徴量を graph_node テーブルに格納する。

        feats 列には次の4グループに分けた JSON を保存する：
            {"cont": {連続値特徴量}, "cat": {カテゴリの整数ID}, "date": {経過日数}, "label": {目的変数}}
        - cont : そのままモデルの x として使う
        - cat  : モデル側で列ごとに nn.Embedding する（get_vocab_sizes()でサイズ取得）
        - date : モデル側で Time2Vec 等の時間エンコーディングに渡す
        - label: LABEL_COLUMNS[node_type] に登録された目的変数（例: stock の y / y_valid）。
                 cont とは完全に分離し、data[node_type][列名] として別テンソルになる
                 （fetch_node_table() 参照）。誤って cont に混ざるとモデルがラベルを
                 そのまま入力として受け取るリークになるため、cont_cols からは必ず除外し、
                 かつ「y」「y_」始まりの列が cont_cols に残っていないかもガードする。
        """
        using_df_list = [
            (self.financials_df.copy(), "statement"),
            (self.prices_df.copy(), "stock"),
            (self.options_df.copy(), "option"),
            (self.futures_df.copy(), "future"),
        ]

        for i, (df, node_type) in enumerate(using_df_list, start=1):
            if "week_id" not in df.columns or "Code" not in df.columns:
                raise ValueError("DataFrame must contain 'week_id' and 'Code' columns.")

            print(f"Processing node_type: {node_type} ({i}/{len(using_df_list)})")

            cat_cols = CATEGORICAL_COLUMNS.get(node_type, [])
            date_cols = DATE_COLUMNS.get(node_type, [])
            label_cols = LABEL_COLUMNS.get(node_type, [])
            exclude_cols = {"week_id", "Code", *cat_cols, *date_cols, *label_cols}
            cont_cols = [c for c in df.columns if c not in exclude_cols]

            # 安全弁: LABEL_COLUMNS への登録漏れ等で目的変数らしき列
            # （"y" 単体 / "y_" 始まり）が cont_cols に紛れ込んでいないか検査する。
            # 正規のバックテスト用リターン列 "r_i"/"r_m"/"r_f" は先頭が "y" ではないため
            # このガードには掛からない。
            leaked = [c for c in cont_cols if _LABEL_LIKE_COLUMN_RE.match(c)]
            if leaked:
                raise ValueError(
                    f"[{node_type}] 目的変数らしき列が連続値特徴量(cont)に混入しようとしています: "
                    f"{leaked}. LABEL_COLUMNS['{node_type}'] に追加して cont_cols から除外してください。"
                )

            # カテゴリ列を事前に整数化（保存済みvocabを使用）
            cat_encoded: Dict[str, np.ndarray] = {}
            for col in cat_cols:
                vocab = load_vocab(vocab_path(self.vocab_dir, self.serial_id, node_type, col))
                cat_encoded[col] = encode_category(df[col].values, vocab)

            # 日付列を経過日数(float)に変換
            date_encoded: Dict[str, np.ndarray] = {}
            for col in date_cols:
                date_encoded[col] = date_to_days_since_epoch(df[col])

            # 目的変数列（cont とは分離して保持する）
            label_encoded: Dict[str, np.ndarray] = {}
            for col in label_cols:
                label_encoded[col] = df[col].to_numpy(dtype=FEATURE_FLOAT_DTYPE)

            for batch_start in range(0, len(df), 1000):
                batch_end = min(batch_start + 1000, len(df))
                print(f"\rProcessing batch: {batch_start} to {batch_end} ({i}/{len(using_df_list)})", end="")

                df_batch = df.iloc[batch_start:batch_end]
                batch_node_id = df_batch.apply(
                    lambda row: f'{node_type}_{int(row["week_id"])}_{row["Code"]}', axis=1
                )
                df_cont_only = df_batch[cont_cols]

                batch_feats = []
                for row_pos in range(len(df_batch)):
                    g = batch_start + row_pos  # 元dfにおけるグローバル行位置
                    payload = {
                        "cont": df_cont_only.iloc[row_pos].to_dict(),
                        "cat": {col: int(cat_encoded[col][g]) for col in cat_cols},
                        "date": {col: float(date_encoded[col][g]) for col in date_cols},
                        "label": {col: float(label_encoded[col][g]) for col in label_cols},
                    }
                    batch_feats.append(json.dumps(payload))

                batch_feats_num = [len(cont_cols)] * len(df_batch)

                insert.feats(pd.DataFrame({
                    "node_id": batch_node_id,
                    "feats": batch_feats,
                    "feats_num": batch_feats_num,
                }), self.serial_id)
            print()

    # ------------------------------------------------------------------
    # 5. まとめて実行
    # ------------------------------------------------------------------
    def insert_to_graph_info_table(self):
        """データベースにノード情報とエッジ情報を登録する。"""
        edge_func_list = [
            self.statement_prev_statement_preprocess,
            self.statement_report_stock_preprocess,
            self.stock_corr_stock_preprocess,
            self.option_corr_option_preprocess,
            self.option_prev_option_preprocess,
            self.future_corr_future_preprocess,
            self.future_prev_future_preprocess,
            self.stock_derivative_option_preprocess,
            self.stock_derivative_future_preprocess,
            self.node_id_define,
            self.build_category_vocabs,  # node_feats_define より前に vocab を確定させておく
            self.node_feats_define,
        ]
        for func in edge_func_list:
            now = dt.now()
            func()
            print("preprocess time", dt.now() - now)


class graphDataSet(InMemoryDataset):
    """全期間・全銘柄・全ノードタイプを含む「単一の」HeteroData を保持するデータセット。

    train/val/test の分割はここでは行わない（get_loaders 側でマスクとして行う）。
    """

    def __init__(self, root, transform=None, pre_transform=None, serial_id: int = 1,
                 vocab_dir: str = DEFAULT_VOCAB_DIR):
        self.serial_id = serial_id
        self.vocab_dir = vocab_dir
        _allow_numpy_globals_for_torch_load()  # weights_only=True での復元を可能にする
        super().__init__(root, transform, pre_transform)
        self.load(self.processed_paths[0])

    @property
    def raw_file_names(self) -> List[str]:
        return []

    @property
    def processed_file_names(self) -> List[str]:
        # 単一グラフのみを保持するため、ファイルは1つでよい
        return [f"data_{self.serial_id}_full.pt"]

    @property
    def num_classes(self) -> int:
        return 2

    def download(self) -> None:
        pass

    def _ensure_db_built(self) -> None:
        """raw データの DB 登録（前処理）が未実行なら実行する。"""
        db_path = cf.PATH_GRAPHINFO_DB.safe_substitute(serial_id=self.serial_id)
        if os.path.exists(db_path):
            return

        create.graph_info(self.serial_id)
        pp = preprocess(
            financials_df=fetch.financials(),
            prices_df=fetch.prices(),
            options_df=fetch.options(),
            futures_df=fetch.futures(),
            serial_id=self.serial_id,
            vocab_dir=self.vocab_dir,
        )
        pp.insert_to_graph_info_table()

    def _node_str_id_path(self, node_type: str) -> str:
        """node_str_id を保存する .npy ファイルのパス。

        HeteroData の中には入れず、別ファイルとして保存する
        （NeighborLoader が全ノード属性を自動でテンソル化しようとするため、
        文字列配列を data[node_type] に直接持たせると
        TypeError: can't convert np.ndarray of type numpy.str_ になる）。
        """
        return os.path.join(self.processed_dir, f"node_str_id_{self.serial_id}_{node_type}.npy")

    def load_node_str_id(self, node_type: str) -> np.ndarray:
        """指定 node_type の node_str_id 配列をロードする。

        使い方（学習ループ内でバッチの正体を特定したい場合）:
            global_idx = batch['stock'].n_id.numpy()  # NeighborLoaderが自動付与
            str_ids = dataset.load_node_str_id('stock')[global_idx]
        """
        return np.load(self._node_str_id_path(node_type), allow_pickle=False)

    def _build_full_graph(self) -> HeteroData:
        """DB から全エッジ・全ノードを取得し、単一の HeteroData を構築する。"""
        data = HeteroData()

        # 1. 先にノード側を読み込み、node_id文字列 -> ローカル整数インデックス の
        #    辞書を node_type ごとに作っておく（エッジ側の整数化に必要なため）
        node_id_to_idx: Dict[str, Dict[str, int]] = {}
        for node_type in ["stock", "statement", "option", "future"]:
            node_table = fetch_node_table(self.serial_id, node_type)
            data[node_type].x = torch.tensor(node_table["x"], dtype=TORCH_FLOAT_DTYPE)
            data[node_type].cat_x = torch.tensor(node_table["cat_x"], dtype=torch.long)   # (N, カテゴリ列数)
            data[node_type].date_x = torch.tensor(node_table["date_x"], dtype=TORCH_FLOAT_DTYPE)  # (N, 日付列数)
            # 目的変数（例: stock の y / y_valid）。x とは別テンソルとして持たせる
            # （LABEL_COLUMNS[node_type] が空なら label_x は (N, 0) で何も生えない）
            for label_idx, label_col in enumerate(LABEL_COLUMNS.get(node_type, [])):
                data[node_type][label_col] = torch.tensor(
                    node_table["label_x"][:, label_idx], dtype=TORCH_FLOAT_DTYPE
                )
            data[node_type].is_target = torch.tensor(node_table["is_target"], dtype=torch.bool)
            data[node_type].time_id = torch.tensor(node_table["time_id"], dtype=torch.long)
            # 文字列IDは HeteroData に入れず .npy として別保存する（理由は _node_str_id_path 参照）
            os.makedirs(self.processed_dir, exist_ok=True)
            np.save(self._node_str_id_path(node_type), node_table["node_str_id"])

            node_id_to_idx[node_type] = build_node_id_to_idx(node_table["node_str_id"])

        # 2. エッジ側（まだ文字列 node_id のまま）を取得
        edge_src_str, edge_dst_str = fetch_edge_index(self.serial_id)  # それぞれ (E,) の文字列配列
        edge_type = fetch_edge_attr(self.serial_id, "edge_type")
        edge_weight = fetch_edge_attr(self.serial_id, "edge_weight")
        edge_time = fetch_edge_attr(self.serial_id, "observable_time_id")

        edge_type_names = sorted(set(edge_type))
        for edge_type_name in edge_type_names:
            src_t, rel, dst_t = edge_type_name.split("__")
            idx = np.where(edge_type == edge_type_name)[0]

            # 文字列 node_id -> 整数インデックス に変換してから tensor化する
            edge_index_int = map_edge_ids_to_idx(
                edge_src_str[idx], edge_dst_str[idx],
                node_id_to_idx[src_t], node_id_to_idx[dst_t],
            )

            data[src_t, rel, dst_t].edge_index = torch.tensor(edge_index_int, dtype=torch.long)
            data[src_t, rel, dst_t].edge_weight = torch.tensor(edge_weight[idx], dtype=TORCH_FLOAT_DTYPE)
            data[src_t, rel, dst_t].edge_time = torch.tensor(edge_time[idx], dtype=torch.long)

            # 逆エッジを必要とする関係なら追加する
            key = (src_t, rel, dst_t)
            if key in REVERSE_RELATIONS:
                rev_rel = REVERSE_RELATIONS[key]
                rev_edge_index = edge_index_int[[1, 0], :]  # src/dst を入れ替え
                data[dst_t, rev_rel, src_t].edge_index = torch.tensor(rev_edge_index, dtype=torch.long)
                data[dst_t, rev_rel, src_t].edge_weight = torch.tensor(edge_weight[idx], dtype=TORCH_FLOAT_DTYPE)
                data[dst_t, rev_rel, src_t].edge_time = torch.tensor(edge_time[idx], dtype=torch.long)

        return data

    def process(self) -> None:
        self._ensure_db_built()
        data = self._build_full_graph()
        self.save([data], self.processed_paths[0])


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


def mock_code(serial_id: int = 1):
    train_loader, val_loader, test_loader = get_loaders(serial_id=serial_id, split_1_per=0.7, split_2_per=0.85, batch_size=32)

    for batch in train_loader:
        print(batch)
    for batch in val_loader:
        print(batch)
    for batch in test_loader:
        print(batch)