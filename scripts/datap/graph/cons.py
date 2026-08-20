import torch

class related_fetch:
    # FETCH DATA CONSTANTS
    PATH_DB = "./db/synthesis/synthesis.duckdb"
    PATH_SQL_TO_FETCH_PRICES = "./graph_lab/sql/get_table_to_CAPM.sql"
    PATH_SQL_TO_FETCH_FINANCIALS = "./graph_lab/sql/get_fin_data_by_week.sql"
    YEAR_START = 2011
    YEAR_END = 2025

class train_constants:
    # BUILD TRAIN DATASET CONSTANTS
    RESIDUAL_STORED_PATH = "./scripts/datap/graph/edge_matrix/store/returns_residual_matrix.parquet"
    GRAPH_STORED_PATH = "./scripts/datap/graph/edge_matrix/store/graph.pkl"
    TRAIN_START_YEAR = 2015
    ROLLING_WINDOW = 52
    WINDOW_SIZE = 52
    THRESHOLD = 0.7
    FIRST_WEEK_ID = 201501
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

class print_constants:
    # COLOR FOR PRINT FUNCTION
    CLEAR = '\033[2K'
    MAGENTA = '\033[35m'
    RESET = '\033[0m'