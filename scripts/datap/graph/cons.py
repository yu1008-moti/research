from string import Template
from typing import List, Optional


class graph_params:
    """グラフ構築に関わる、ユーザーが調整し得るハイパーパラメータをまとめたクラス。

    capm_corr.py / derivative_corr.py / data_pipeline.py の各関数は、
    引数を明示的に渡さなかった場合にここの値をデフォルトとして参照する。
    値を変えたい場合は、このクラスの値を直接書き換えるか、各関数呼び出し時に
    キーワード引数で個別に上書きすればよい（両方の変更手段に対応している）。
    """

    # ------------------------------------------------------------------
    # stock__corr__stock （CAPM残差相関, capm_corr.py）
    # ------------------------------------------------------------------
    CAPM_WINDOW_SIZE_FOR_CAPM: int = 52
    """CAPM をローリング推定する窓（週）。"""
    CAPM_WINDOW_SIZE_FOR_CORR: int = 52
    """CAPM残差リターンのローリング相関を取る窓（週）。"""
    CAPM_THRESHOLD: float = 0.7
    """|corr| > CAPM_THRESHOLD の銘柄ペアのみエッジ化する。"""
    CAPM_FIRST_WEEK_ID: int = 201501
    """この週ID以降のみ stock__corr__stock エッジを生成する。"""
    CAPM_RESIDUAL_STORED_PATH: str = "./scripts/datap/graph/store/returns_residual_matrix.parquet"
    """CAPM残差行列のキャッシュ先。"""
    CAPM_DEVICE: Optional[str] = None
    """None の場合は cuda が使えれば cuda、無ければ cpu を自動選択する。"""

    # ------------------------------------------------------------------
    # Option__corr__Option / Future__corr__Future （derivative_corr.py）
    # ------------------------------------------------------------------
    DERIVATIVE_CORR_WINDOW_SIZE: int = 8
    """相関を取るローリング窓（週）。契約寿命が短いため株式(52週)より小さめにしてある。"""
    DERIVATIVE_CORR_MIN_PERIODS: int = 4
    """窓内で相関を計算するために最低限必要な観測週数。"""
    DERIVATIVE_CORR_THRESHOLD: float = 0.7
    """|corr| > DERIVATIVE_CORR_THRESHOLD のペアのみエッジ化する。
    下げるとエッジ数が非線形に急増し得るので注意
    （claude_output配下のメモリ試算メモも参照）。"""

    # ------------------------------------------------------------------
    # Stock__derivative__Future （data_pipeline.py）
    # ------------------------------------------------------------------
    MARKET_INDEX_FUTURE_PRODCATS: List[str] = ["NK225F", "TOPIXF"]
    """全対象銘柄を接続する「主要な株価指数先物」の商品区分。
    先物は個別株の原資産を持たないため、この区分の期近物に一律接続する。"""

    # ------------------------------------------------------------------
    # ノード特徴量・vocab（data_pipeline.py）
    # ------------------------------------------------------------------
    DEFAULT_VOCAB_DIR: str = "scripts/datap/graph/DS/vocab"
    """カテゴリ変数 vocab（{値: 整数ID}）の保存先ディレクトリ。"""
    TIME_ENCODING_EPOCH: str = "2000-01-01"
    """Time2Vec 等の時間エンコーディングの基準日（この日からの経過日数を特徴量にする）。"""

    # ------------------------------------------------------------------
    # get_loaders（train/val/test split・近傍サンプリング, data_pipeline.py）
    # ------------------------------------------------------------------
    SPLIT_1_PER: float = 0.7
    """train と val の境界（time_idの範囲に対する割合）。"""
    SPLIT_2_PER: float = 0.85
    """val と test の境界（time_idの範囲に対する割合）。"""
    BATCH_SIZE: int = 32
    """NeighborLoader のバッチサイズ。"""
    NUM_NEIGHBORS_PER_HOP: int = 10
    """num_neighbors を明示指定しなかった場合、全エッジ種別に一律で使う
    「1ホップあたりの近傍サンプル数」。関係ごとに変えたい場合は
    get_loaders() の num_neighbors 引数で個別に上書きすること。"""
    NUM_HOPS: int = 2
    """NeighborLoader のホップ数（= num_neighbors のリスト長）。"""


class rel_sql:
    ## DATABASE PATHS
    PATH_ORIGINAL_DB = "./db/synthesis/synthesis.duckdb"
    PATH_GRAPHINFO_DB = Template("./scripts/datap/graph/DS/graph_info_${serial_id}.duckdb")

    ## SQL FILE PATHS
    PATH_SQL_TO_FETCH_PRICES = "./scripts/datap/graph/sql/get_table_to_CAPM.sql"
    PATH_SQL_TO_FETCH_FINANCIALS = "./scripts/datap/graph/sql/get_fin_data_by_week.sql"
    PATH_SQL_TO_FETCH_OPTIONS = "./scripts/datap/graph/sql/get_table_to_option.sql"
    PATH_SQL_TO_FETCH_FUTURES = "./scripts/datap/graph/sql/get_table_to_future.sql"

    PATH_SQL_TO_INSERT_TO_FEATS_TABLE = "./scripts/datap/graph/sql/insert_to_feats_table.sql"
    PATH_SQL_TO_INSERT_TO_NODE_TABLE = "./scripts/datap/graph/sql/insert_to_node_table.sql"
    PATH_SQL_TO_INSERT_TO_EDGE_TABLE = "./scripts/datap/graph/sql/insert_to_edge_table.sql"

    PATH_SQL_TO_CREATE_GRAPHINFO_TABLE = "./scripts/datap/graph/sql/create_graph_info_table.sql"

    # SQL PARAMETERS
    START_WEEK_ID = 200819
    END_WEEK_ID = 202616