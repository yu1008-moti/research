from scripts.datap.graph_v2.sql import fetch
from scripts.datap.graph_v2 import capm_corr

prices_df = fetch.prices()

# 銘柄間 CAPM 残差相関エッジ (週 ID -> (edge_index, edge_weight))
firm_corr = capm_corr.build_firm_corr_edges(prices_df)