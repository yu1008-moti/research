import torch

class related_fetch:
    # FETCH DATA CONSTANTS

    ## DATABASE PATHS
    PATH_ORIGINAL_DB = "./db/synthesis/synthesis.duckdb"
    PATH_GRAPHINFO_DB = "./scripts/datap/graph_v2/store/graph_info.duckdb"

    ## SQL FILE PATHS
    PATH_SQL_TO_FETCH_PRICES = "./scripts/datap/graph_v2/sql/get_table_to_CAPM.sql"
    PATH_SQL_TO_FETCH_FINANCIALS = "./scripts/datap/graph_v2/sql/get_fin_data_by_week.sql"
    PATH_SQL_TO_INSERT_TO_NODE_TABLE = "./scripts/datap/graph_v2/sql/insert_to_node_table.sql"
    PATH_SQL_TO_INSERT_TO_EDGE_TABLE = "./scripts/datap/graph_v2/sql/insert_to_edge_table.sql"
    YEAR_START = 2011
    YEAR_END = 2025