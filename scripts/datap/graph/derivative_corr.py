"""Option / Future ノード間の相関エッジ (Option__corr__Option, Future__corr__Future) を構築する。

capm_corr.py の株式 CAPM 残差相関とは異なる方式を取る:

- デリバティブ契約は満期のある短命なインスタンス（オプションは全期間で約27万契約）であり、
  かつ「何と比較すべきか」が銘柄のように単一の市場ポートフォリオでは定義できないため、
  CAPM 残差ではなく「同じグループ（原資産 UndSSO / 商品区分 ProdCat）内の生の週次収益率」の
  ローリング相関を使う。グループ分けは呼び出し側（data_pipeline.preprocess）が指定する。
- 契約の寿命が株式の52週ローリング窓よりずっと短いことが多いため、既定のウィンドウは
  株式よりかなり短めにしてある（scripts/datap/graph/cons.py の graph_params 参照）。

ハイパーパラメータ（窓幅・閾値・最小観測数）は全て scripts/datap/graph/cons.py の
graph_params（DERIVATIVE_CORR_* 系）に集約されている。
"""

from __future__ import annotations

from typing import Dict, List, NamedTuple, Tuple

import numpy as np
import pandas as pd

from scripts.datap.graph.cons import graph_params


class PeerCorrEdges(NamedTuple):
    """ピアグループ内相関エッジの構築結果。

    Attributes:
        edges: ``week_id -> [(src_code, dst_code, weight), ...]``。
            相関行列は対称なので (i, j) と (j, i) の両方向が入っている。
    """

    edges: Dict[int, List[Tuple[str, str, float]]]


def _weekly_return(df: pd.DataFrame, code_col: str, close_col: str) -> pd.DataFrame:
    """Code ごとに週次終値（対数値）の差分を「収益率」として付与する。"""
    work = df.sort_values([code_col, "week_id"]).copy()
    work["ret"] = work.groupby(code_col)[close_col].diff()
    return work


def build_peer_corr_edges(
    df: pd.DataFrame,
    *,
    group_col: str,
    code_col: str = "Code",
    close_col: str = "AdjC",
    window: int = graph_params.DERIVATIVE_CORR_WINDOW_SIZE,
    threshold: float = graph_params.DERIVATIVE_CORR_THRESHOLD,
    min_periods: int = graph_params.DERIVATIVE_CORR_MIN_PERIODS,
) -> PeerCorrEdges:
    """``group_col``（UndSSO や ProdCat）が同じ契約同士について、週次収益率のローリング相関を計算する。

    ``group_col`` が NULL の行（原資産の無い指数・債券オプション等）は対象外にする。

    ★ 性能について
    グループ（＝原資産1銘柄）が「過去に一度でも上場した契約」の列を全て持つピボット表を
    素朴に ``rolling().corr()`` すると、同時に生存している契約は数個〜数十個程度でも、
    列数自体は上場・満期を繰り返した契約の総数（オプションでは1銘柄あたり数千契約になり得る）
    まで膨れ上がり、O(週数 × 契約数^2) の相関計算がボトルネックになる
    （実測で1グループが数分〜到達しないレベルまで悪化した）。
    そのため、各週ごとに「直近 ``window`` 週で ``min_periods`` 週以上データがある契約」
    にだけ列を絞り込んでから ``DataFrame.corr()`` を呼ぶ（この絞り込み自体は
    O(週数 × 契約数) の notna 集計のみで済み、相関計算は同時生存契約数だけの
    小さな正方行列に対して行われる）。
    """
    work = _weekly_return(df, code_col, close_col)
    work = work.dropna(subset=[group_col])

    edges: Dict[int, List[Tuple[str, str, float]]] = {}
    groups = work[group_col].unique()
    n_groups = len(groups)

    for gi, key in enumerate(groups, start=1):
        print(f"\r[peer_corr:{group_col}] group {gi}/{n_groups}: {key}", end=" ")
        sub = work[work[group_col] == key]
        if sub[code_col].nunique() < 2:
            continue

        pivot = sub.pivot_table(index="week_id", columns=code_col, values="ret").sort_index()
        if pivot.shape[1] < 2:
            continue

        # "今週ノードが実在するか" を判定する存在テーブル。ret は diff() の都合上、
        # 契約が上場した最初の週は非NULLの行があっても NaN になる（notna(pivot) では
        # 存在しない扱いになってしまう）ため、ret とは別に純粋な行の存在だけを見る。
        exists = sub.assign(_present=1).pivot_table(index="week_id", columns=code_col, values="_present", aggfunc="max")
        exists = exists.reindex(index=pivot.index, columns=pivot.columns).notna()

        notna = pivot.notna()
        week_ids = pivot.index.to_numpy()

        for t in range(len(week_ids)):
            lo = max(0, t - window + 1)
            active_count = notna.iloc[lo:t + 1].sum(axis=0)
            # 窓内で十分な相関計算用データがあり、かつ「今週」実際にノードが存在する契約のみを対象にする。
            # そうしないと、直近数週データが欠けている契約に対してダングリングエッジ
            # （存在しないノードを指すエッジ）を作ってしまう。
            active_cols = active_count.index[(active_count >= min_periods) & exists.iloc[t]]
            if len(active_cols) < 2:
                continue

            win = pivot.iloc[lo:t + 1][active_cols]
            corr = win.corr().to_numpy(copy=True)
            np.fill_diagonal(corr, 0.0)
            idx_i, idx_j = np.where(np.abs(corr) > threshold)
            if len(idx_i) == 0:
                continue

            codes = active_cols.to_numpy()
            week_edges = edges.setdefault(int(week_ids[t]), [])
            for i, j in zip(idx_i, idx_j):
                week_edges.append((str(codes[i]), str(codes[j]), float(corr[i, j])))

    print()
    return PeerCorrEdges(edges=edges)
