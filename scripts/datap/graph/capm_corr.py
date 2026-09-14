"""銘柄 (Firm) ノード間の CAPM 残差リターンのローリング相関にもとづく隣接行列を構築する。

graph_v1 の以下を単一モジュールに集約して移植したもの:

- ``graph_v1/edge_matrix/constructor/spacial_c.py`` の ``_utils_firm2firm``
  (``_rolling_capm_residual`` / ``_add_capm_factors_column`` / ``_iter_prices_adjacent_matrix``)
- ``graph_v1/edge_matrix/constructor/spacial_c.py`` の ``Spacial.register_firm2firm_edge``
- ``graph_v1/edge_matrix/constructor/utils.py`` の ``u_common`` (週次進捗表示)

graph_v1 との違い:

- 出力は PyG 形式。週 ID ごとに ``edge_index (2, E)`` と ``edge_weight (E,)`` を返す
  (``('firm', 'corr', 'firm')`` の HeteroData にそのまま入れられる)。
- SQL 取得層には依存せず、価格 DataFrame か残差行列を引数で受け取る。
- CAPM 残差行列は parquet キャッシュ、相関計算は週次で進捗表示する点は graph_v1 と同じ。

想定する価格 DataFrame の列 (``scripts/datap/graph_v2/sql/get_table_to_CAPM.sql`` の出力):

    week_id, Code, r_i (個別リターン), r_m (市場リターン), r_f (無リスク金利), ...
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator, List, NamedTuple, Optional, Tuple, Dict

import numpy as np
import pandas as pd
import statsmodels.api as sm
import torch
from statsmodels.regression.rolling import RollingOLS

from scripts.datap.graph.cons import graph_params

# ハイパーパラメータは全て scripts/datap/graph/cons.py の graph_params
# （CAPM_* 系）に集約されている。ここではそのデフォルト値を関数シグネチャの
# デフォルト引数として使うだけで、値そのものの定義は持たない。


class _color:
    """進捗表示用の ANSI エスケープ (graph_v1/cons.py print_constants 相当)。"""

    CLEAR = "\033[2K"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    RESET = "\033[0m"


class FirmCorrEdges(NamedTuple):
    """CAPM 残差相関エッジの構築結果。

    Attributes:
        firm_id_order: エッジ行列の行 / 列に対応する銘柄コードの並び (残差計算後に確定)。
        edges: ``week_id -> (edge_index (2, E) long, edge_weight (E,) float32)``。
            相関行列は対称なので (i, j) と (j, i) の両方向が入っている。
    """

    firm_id_order: pd.Index
    edges: Dict[int, Tuple[torch.Tensor, torch.Tensor]]  # week_id -> (edge_index, edge_weight)


# --------------------------------------------------------------------------- #
# 進捗表示 (graph_v1/edge_matrix/constructor/utils.py u_common の移植)
# --------------------------------------------------------------------------- #
def _display_iter(
    task_summary: str,
    week_id: Optional[int] = None,
    processing_ratio: Optional[float] = None,
    sparse_edge_matrix: Optional[torch.Tensor] = None,
) -> None:
    """``\\r`` で行を上書きしながら週次の進捗を表示する。"""
    parts: List[str] = ["\r", f"TASK [{_color.MAGENTA}{task_summary}{_color.RESET}] "]

    if week_id is not None:
        parts.append(f"week_id: {_color.CYAN}{week_id}{_color.RESET} ")
    if sparse_edge_matrix is not None:
        parts.append(
            f"G Shape: {_color.CYAN}{sparse_edge_matrix.shape[0]} x "
            f"{sparse_edge_matrix.shape[1]}{_color.RESET} "
        )
        parts.append(f"NNZ: {_color.CYAN}{str(sparse_edge_matrix._nnz()).rjust(4)}{_color.RESET} ")
    if processing_ratio is not None:
        parts.append(
            f"Progress: {_color.CYAN}{str(round(processing_ratio * 100, 2)).rjust(6)}%{_color.RESET}"
        )

    end = "\n" if processing_ratio is not None and processing_ratio >= 1.0 else " "
    print(*parts, end=end)


def _display_note(note_title: str, content: object) -> None:
    print(" -", f"Title: [{_color.MAGENTA}{note_title}{_color.RESET}]: ", f"{content}")


# --------------------------------------------------------------------------- #
# CAPM 残差リターンの計算 (graph_v1 _utils_firm2firm の移植)
# --------------------------------------------------------------------------- #
def _rolling_capm_residual(
    stock_ret: pd.Series,
    market_ret: pd.Series,
    window: int = 52,
) -> Tuple[pd.Series, pd.Series]:
    """CAPM を週次ローリング推定し、残差リターンとベータ系列を返す。

    Args:
        stock_ret: 個別株の超過リターン系列 (r_i - r_f)。
        market_ret: 市場の超過リターン系列 (r_m - r_f)。
        window: ローリングウィンドウのサイズ (週)。
    """
    df = pd.concat([stock_ret, market_ret], axis=1, keys=["r_i", "r_m"])
    X = sm.add_constant(data=df["r_m"])

    # statsmodels の RollingOLS は窓長に満たない場合にエラーを出すので、窓長に満たない場合は通常の OLS を使う
    # print(len(df), window, end=" ")
    rres = RollingOLS(endog=df["r_i"], exog=X, window=window).fit()

    fitted = rres.params["const"] + rres.params["r_m"] * df["r_m"]
    residual = df["r_i"] - fitted
    return residual, rres.params["r_m"]


def residual_matrix_from_prices(
    prices_df: pd.DataFrame,
    *,
    window_size_for_capm: int = graph_params.CAPM_WINDOW_SIZE_FOR_CAPM,
    residual_stored_path: str = graph_params.CAPM_RESIDUAL_STORED_PATH,
    use_cache: bool = True,
) -> pd.DataFrame:
    """全銘柄の CAPM 残差リターンを計算し ``week_id x Code`` 行列にピボットする。

    ``residual_stored_path`` に parquet が存在すればそれをロードして計算をスキップする。
    窓長に満たない銘柄は除外し、除外率 / 有効銘柄数を表示する。

    Args:
        prices_df: ``week_id, Code, r_i, r_m, r_f`` を含む価格 DataFrame。
        window_size_for_capm: CAPM ローリング推定の窓 (週)。
        residual_stored_path: 残差行列 parquet のキャッシュ先。
        use_cache: True かつキャッシュが存在すればロードのみ行う。

    Returns:
        ``week_id`` を index、``Code`` を columns、残差リターンを値とする DataFrame。
    """
    cache_path = Path(residual_stored_path)
    if use_cache and cache_path.exists():
        _display_note(
            "Returns Residual Matrix already exists",
            "Skip the calculation of CAPM factors by rolling regression",
        )
        return pd.read_parquet(cache_path)

    prices_df = prices_df.copy().dropna()
    prices_df["residual"] = np.nan
    prices_df["beta"] = np.nan

    codes = prices_df["Code"].unique()
    codes_length = len(codes)
    unmatched_codes: List[Tuple[str, int]] = []

    for i, code in enumerate(codes):
        _display_iter(
            "calculate CAPM factors by rolling regression",
            processing_ratio=(i + 1) / codes_length,
        )

        mask: pd.Series = prices_df["Code"] == code
        filtered = prices_df[mask]
        if len(filtered) < window_size_for_capm:
            unmatched_codes.append((code, len(filtered)))
            continue

        stock_returns = filtered["r_i"] - filtered["r_f"]
        market_returns = filtered["r_m"] - filtered["r_f"]
        residuals, betas = _rolling_capm_residual(
            stock_returns, market_returns, window=window_size_for_capm
        )
        prices_df.loc[filtered.index, "residual"] = residuals
        prices_df.loc[filtered.index, "beta"] = betas

    prices_df = prices_df[~prices_df["residual"].isna() & ~prices_df["beta"].isna()]

    _display_note(
        "Numbers of Codes have Unmatched length of Array",
        f"{len(unmatched_codes)} is unmatched: "
        f"{round(len(unmatched_codes) / codes_length, 2)}%",
    )
    _display_note(
        "Numbers of Available Codes",
        f"{len(prices_df['Code'].unique())} is available: "
        f"{round((codes_length - len(unmatched_codes)) / codes_length, 2)}%",
    )

    residual_matrix = prices_df.pivot(index="week_id", columns="Code", values="residual")

    if use_cache:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        residual_matrix.to_parquet(cache_path, engine="pyarrow")

    return residual_matrix


# --------------------------------------------------------------------------- #
# 残差行列 -> 週次ローリング相関 -> 疎行列 (graph_v1 _iter_prices_adjacent_matrix の移植)
# --------------------------------------------------------------------------- #
def _iter_rolling_corr_sparse(
    residual_matrix: pd.DataFrame,
    window_size_for_corr: int,
    residuals_threshold: float,
    device: str,
) -> Iterator[Tuple[float, int, torch.Tensor]]:
    """残差行列に対し、和 / グラム行列を差分更新しながら週次のローリング相関を計算する。

    対角を 0 にし ``|corr| > threshold`` のみ残した疎テンソルを
    ``(進捗率, week_id, 疎相関行列)`` として yield する。
    """
    returns_residual = torch.tensor(residual_matrix.values, dtype=torch.float32, device=device)
    returns_week_id: List[int] = residual_matrix.index.values.tolist()

    T, _ = returns_residual.shape

    buf = returns_residual[:window_size_for_corr]  # (window, N)
    s1 = torch.sum(buf, dim=0)  # (N,)  和
    G = buf.T @ buf  # (N, N) グラム行列

    for t in range(window_size_for_corr, T):
        mean = s1 / window_size_for_corr
        cov = G / window_size_for_corr - torch.outer(mean, mean)
        std = torch.sqrt(torch.diag(cov))
        corr = cov / torch.outer(std, std)
        corr = torch.nan_to_num(corr, nan=0.0)
        corr.fill_diagonal_(0)
        mask = torch.abs(corr) > residuals_threshold

        yield (t + 1) / T, returns_week_id[t], (corr * mask).to_sparse()

        # スライド: 新しい週を追加、最も古い週を除去
        x_new = returns_residual[t]
        x_old = returns_residual[t - window_size_for_corr]
        s1 += x_new - x_old
        G += torch.outer(x_new, x_new) - torch.outer(x_old, x_old)


def _sparse_corr_to_edge_index(sparse_corr: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
    """疎な相関行列を PyG の ``edge_index`` / ``edge_weight`` に変換する。"""
    s = sparse_corr.coalesce()
    edge_index = s.indices().to(torch.long).cpu()
    edge_weight = s.values().to(torch.float32).cpu()
    return edge_index, edge_weight


# --------------------------------------------------------------------------- #
# 公開 API
# --------------------------------------------------------------------------- #
def iter_firm_corr_edges(
    *,
    prices_df: Optional[pd.DataFrame] = None,
    residual_matrix: Optional[pd.DataFrame] = None,
    window_size_for_capm: int = graph_params.CAPM_WINDOW_SIZE_FOR_CAPM,
    window_size_for_corr: int = graph_params.CAPM_WINDOW_SIZE_FOR_CORR,
    threshold: float = graph_params.CAPM_THRESHOLD,
    first_week_id: int = graph_params.CAPM_FIRST_WEEK_ID,
    residual_stored_path: str = graph_params.CAPM_RESIDUAL_STORED_PATH,
    use_cache: bool = True,
    device: Optional[str] = None,
    verbose: bool = True,
) -> Iterator[Tuple[int, torch.Tensor, torch.Tensor, pd.Index]]:
    """週 ID ごとに CAPM 残差相関エッジを yield するジェネレータ。

    ``prices_df`` か ``residual_matrix`` のいずれかを渡す。両方渡した場合は
    ``residual_matrix`` を優先する。

    Yields:
        ``(week_id, edge_index (2, E), edge_weight (E,), firm_id_order)``。
        ``firm_id_order`` は毎回同じオブジェクトを返す (行 / 列の並び)。
    """
    if residual_matrix is None:
        if prices_df is None:
            raise ValueError("prices_df か residual_matrix のどちらかを渡してください。")
        residual_matrix = residual_matrix_from_prices(
            prices_df,
            window_size_for_capm=window_size_for_capm,
            residual_stored_path=residual_stored_path,
            use_cache=use_cache,
        )

    # 残差計算で全 NaN の銘柄が落ちるため、並びは計算後に確定する
    firm_id_order = residual_matrix.columns
    # device 未指定時: graph_params.CAPM_DEVICE (Noneならcuda自動判定) の順に採用
    device = device or graph_params.CAPM_DEVICE or ("cuda" if torch.cuda.is_available() else "cpu")

    for ratio, week_id, sparse_corr in _iter_rolling_corr_sparse(
        residual_matrix, window_size_for_corr, threshold, device
    ):
        if week_id < first_week_id:
            continue

        edge_index, edge_weight = _sparse_corr_to_edge_index(sparse_corr)

        if verbose:
            _display_iter(
                "build firm2firm CAPM-residual corr edges weekly",
                week_id=week_id,
                processing_ratio=ratio,
                sparse_edge_matrix=sparse_corr,
            )

        yield week_id, edge_index, edge_weight, firm_id_order


def build_firm_corr_edges(
    prices_df: Optional[pd.DataFrame] = None,
    *,
    residual_matrix: Optional[pd.DataFrame] = None,
    window_size_for_capm: int = graph_params.CAPM_WINDOW_SIZE_FOR_CAPM,
    window_size_for_corr: int = graph_params.CAPM_WINDOW_SIZE_FOR_CORR,
    threshold: float = graph_params.CAPM_THRESHOLD,
    first_week_id: int = graph_params.CAPM_FIRST_WEEK_ID,
    residual_stored_path: str = graph_params.CAPM_RESIDUAL_STORED_PATH,
    use_cache: bool = True,
    device: Optional[str] = None,
    verbose: bool = True,
) -> FirmCorrEdges:
    """全週分の CAPM 残差相関エッジをまとめて構築する。

    Args と各パラメータの意味は :func:`iter_firm_corr_edges` と同じ。

    Returns:
        FirmCorrEdges: ``firm_id_order`` と ``week_id -> (edge_index, edge_weight)`` の辞書。
    """
    edges: dict = {}
    firm_id_order: Optional[pd.Index] = None

    for week_id, edge_index, edge_weight, order in iter_firm_corr_edges(
        prices_df=prices_df,
        residual_matrix=residual_matrix,
        window_size_for_capm=window_size_for_capm,
        window_size_for_corr=window_size_for_corr,
        threshold=threshold,
        first_week_id=first_week_id,
        residual_stored_path=residual_stored_path,
        use_cache=use_cache,
        device=device,
        verbose=verbose,
    ):
        firm_id_order = order
        edges[week_id] = (edge_index, edge_weight)

    if firm_id_order is None:
        firm_id_order = pd.Index([])

    return FirmCorrEdges(firm_id_order=firm_id_order, edges=edges)
