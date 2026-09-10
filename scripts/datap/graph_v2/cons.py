import torch

class related_fetch:
    # FETCH DATA CONSTANTS
    PATH_DB = "./db/synthesis/synthesis.duckdb"
    PATH_SQL_TO_FETCH_PRICES = "./scripts/datap/graph_v2/sql/get_table_to_CAPM.sql"
    PATH_SQL_TO_FETCH_FINANCIALS = "./scripts/datap/graph_v2/sql/get_fin_data_by_week.sql"
    YEAR_START = 2011
    YEAR_END = 2025