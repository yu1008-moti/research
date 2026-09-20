from string import Template
from typing import List, Optional

import numpy as np
import torch


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
    # is_target（node_id_define）/ Stock__derivative__Future（data_pipeline.py）
    # ------------------------------------------------------------------
    TARGET_STOCK_MKT_CODES: List[str] = ["0000", "0500", "7000"]
    """予測・損失計算対象銘柄（is_target）とみなす eqt_main_tmp.Mkt コード。
    '0000'=旧東証一部、'0500'=プライム（2022/06/27以降）、'7000'=プライム移行期
    コード（2022/04/04〜06/27、sql/synthesis/equities_bars.sql 参照）。
    この移行期コードを含めないと、該当する12週分（time_id 202214〜202225）で
    is_target が全銘柄 False になり学習/評価対象が消失するバグを生む。"""

    # ------------------------------------------------------------------
    # ノード特徴量・vocab（data_pipeline.py）
    # ------------------------------------------------------------------
    DEFAULT_VOCAB_DIR: str = "scripts/datap/graph/DS/vocab"
    """カテゴリ変数 vocab（{値: 整数ID}）の保存先ディレクトリ。"""
    TIME_ENCODING_EPOCH: str = "2000-01-01"
    """Time2Vec 等の時間エンコーディングの基準日（この日からの経過日数を特徴量にする）。"""
    FEATURE_FLOAT_DTYPE: type = np.float32
    """連続値・日付・目的変数特徴量（x / date_x / label_x）を numpy 配列に
    格納する際の浮動小数点精度。data_pipeline.py 内の該当箇所は全てここを参照する。
    変更する場合は TORCH_FLOAT_DTYPE も対応する精度に合わせて変更すること。"""
    TORCH_FLOAT_DTYPE: torch.dtype = torch.float32
    """HeteroData 構築時、x / date_x / label_x / edge_weight を torch.tensor化
    する際の浮動小数点精度。FEATURE_FLOAT_DTYPE と対応させておくこと。"""

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
    """サンプリングのホップ数（NeighborLoader の num_neighbors / HGTLoader の
    num_samples いずれも、このホップ数分のリストとして渡される）。"""
    NUM_WORKERS: int = 0
    """NeighborLoader/HGTLoader のバックグラウンドワーカープロセス数。既定は0
    （メインプロセスのみでサンプリング、現状維持で最も安全）。

    実測（32GB RAM / Windows / serial_id=9999 の全期間グラフ、batch_size=32,
    num_hops=2, num_neighbors_per_hop=10, hidden_dim=64 のベースラインモデルで
    学習ステップを含めて計測）: num_workers=0 で91.8ms/batch、2で36.1ms/batch
    （約2.5倍）、4で35.3ms/batch（2からの追加効果はほぼ無し）。メモリは
    Windows の multiprocessing が spawn 方式でも、PyTorch のテンソルIPCが
    共有メモリ経由で本体の巨大テンソル（グラフ全体、5〜6GB相当）自体は
    複製しないため、ワーカー1つあたりの純増は2〜3GB程度に収まる
    （ワーカーごとに再構築されるCSRサンプリング構造・Pythonインタプリタ分と
    見られる）。32GB環境なら2が費用対効果の頭打ち点で安全マージンも十分。

    ★このデフォルトを0以外に変更しないこと★: Windows の multiprocessing は
    spawn 方式のため、num_workers>0 で呼び出す側は必ず
    `if __name__ == "__main__":` 配下で呼ぶ必要がある（さもないと各ワーカー
    プロセスがモジュールのトップレベルコードを再実行し、呼び出し元の処理が
    ワーカー内で再度実行されてしまう）。本リポジトリの repo root にある
    test_temp.py はこのガード無しに get_loaders() をトップレベルで呼んでいる
    （CLAUDE.md 参照）ため、ここのデフォルトを0以外にすると
    test_temp.py 実行時に壊れる。0より大きい値は、ガード済みの呼び出し元
    （train.py の --num-workers 等）が get_loaders() 呼び出し時に明示的に
    上書きすること。"""

    SAMPLER: str = "neighbor"
    """近傍サンプリング方式。'neighbor'（torch_geometric.loader.NeighborLoader、既定）
    か 'hgt'（torch_geometric.loader.HGTLoader、HGT論文 [Hu+ 2020] の HGSampling を
    使用）を選ぶ。'neighbor' はエッジタイプ単位で一律の近傍数を使うため、
    stock/option/future のようにノード数・次数が大きく異なるタイプが混在する
    ヘテログラフでは、密なタイプ（例: option）がサンプリング／計算コストを
    支配しやすい。'hgt' はノードタイプごとに独立した予算を持ち、次数で
    正規化した重要度でサンプリングするため、この不均衡を緩和できる可能性がある。
    train.py の --sampler で上書き可能。"""
    NUM_SAMPLES_PER_HOP: int = 10
    """HGTLoader 使用時、num_samples を明示指定しなかった場合に全ノードタイプへ
    一律で使う「1ホップあたりのサンプル数」。ノードタイプごとに変えたい場合は
    get_loaders() の num_samples 引数で個別に上書きすること
    （例: option ノードは密なので小さめに絞る等）。"""


class rel_sql:
    ## DATABASE PATHS
    PATH_ORIGINAL_DB = "./db/synthesis/synthesis.duckdb"
    PATH_GRAPHINFO_DB = Template("./scripts/datap/graph/DS/graph_info_${serial_id}.duckdb")

    ## SQL FILE PATHS
    PATH_SQL_TO_FETCH_PRICES = "./sql/graph/get_table_to_CAPM.sql"
    PATH_SQL_TO_FETCH_FINANCIALS = "./sql/graph/get_fin_data_by_week.sql"
    PATH_SQL_TO_FETCH_OPTIONS = "./sql/graph/get_table_to_option.sql"
    PATH_SQL_TO_FETCH_FUTURES = "./sql/graph/get_table_to_future.sql"

    PATH_SQL_TO_INSERT_TO_FEATS_TABLE = "./sql/graph/insert_to_feats_table.sql"
    PATH_SQL_TO_INSERT_TO_NODE_TABLE = "./sql/graph/insert_to_node_table.sql"
    PATH_SQL_TO_INSERT_TO_EDGE_TABLE = "./sql/graph/insert_to_edge_table.sql"

    PATH_SQL_TO_CREATE_GRAPHINFO_TABLE = "./sql/graph/create_graph_info_table.sql"

    # SQL PARAMETERS
    START_WEEK_ID = 200819
    END_WEEK_ID = 202616