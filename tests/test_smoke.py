"""pytest / pythonpath 設定が機能していることを確認するための最小スモークテスト。

DB接続やパイプライン実行は一切行わない（副作用なし）。import できることと、
graph_params の主要な属性が期待通り存在することだけを確認する。
"""

from scripts.datap.graph.cons import graph_params, rel_sql


def test_graph_params_importable():
    assert isinstance(graph_params.CAPM_WINDOW_SIZE_FOR_CAPM, int)
    assert isinstance(graph_params.DERIVATIVE_CORR_THRESHOLD, float)
    assert isinstance(graph_params.MARKET_INDEX_FUTURE_PRODCATS, list)


def test_rel_sql_importable():
    assert hasattr(rel_sql, "PATH_GRAPHINFO_DB")
