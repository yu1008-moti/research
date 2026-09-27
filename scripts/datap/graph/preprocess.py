"""raw データ(financials/prices/options/futures)を graph_node / graph_edge テーブルへ
前処理・格納する `preprocess` クラス。

data_pipeline.py から分離。node_id/is_target/time_id の定義、各エッジタイプの生成、
カテゴリ vocab の構築、node_feats(JSON) の格納までの「DB書き込みまで」の処理を担当する
（HeteroData への読み出しは graph_io.py / dataset.py 側）。
"""

from __future__ import annotations

import json
from datetime import datetime as dt
from typing import Dict, List

import numpy as np
import pandas as pd

from scripts.datap.graph import capm_corr, derivative_corr
from scripts.datap.graph.cons import graph_params
from scripts.datap.graph.feature_encoding import (
    CATEGORICAL_COLUMNS,
    DATE_COLUMNS,
    FEATURE_FLOAT_DTYPE,
    LABEL_COLUMNS,
    LABEL_LIKE_COLUMN_RE,
    build_category_vocab,
    date_to_days_since_epoch,
    encode_category,
    load_vocab,
    save_vocab,
    vocab_path,
)
from scripts.datap.graph.sql import insert

# --------------------------------------------------------------------------
# Stock__derivative__Future で全対象銘柄を接続する「主要な株価指数先物」の商品区分。
# 先物は個別株の原資産を持たない（指数・債券・通貨先物のみ）ため、
# 市場全体のシステマティックリスクを媒介する backbone として、この区分の期近物
# （SQRemainingDays が最小の契約）に全 is_target 銘柄を一律接続する。
# 値の定義は scripts/datap/graph/cons.py の graph_params に集約されている。
# --------------------------------------------------------------------------
MARKET_INDEX_FUTURE_PRODCATS: List[str] = graph_params.MARKET_INDEX_FUTURE_PRODCATS
TARGET_STOCK_MKT_CODES: List[str] = graph_params.TARGET_STOCK_MKT_CODES


class preprocess:
    """データを前処理し、graph_node および graph_edge テーブルに格納する。"""

    def __init__(self, financials_df: pd.DataFrame, prices_df: pd.DataFrame,
                 options_df: pd.DataFrame, futures_df: pd.DataFrame, serial_id: int = 1,
                 vocab_dir: str = graph_params.DEFAULT_VOCAB_DIR):
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
            prices_df["Mkt"].isin(TARGET_STOCK_MKT_CODES)
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
                is_target = df["Mkt"].isin(TARGET_STOCK_MKT_CODES).astype(bool).tolist()
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
                 （graph_io.fetch_node_table() 参照）。誤って cont に混ざるとモデルがラベルを
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
            leaked = [c for c in cont_cols if LABEL_LIKE_COLUMN_RE.match(c)]
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
