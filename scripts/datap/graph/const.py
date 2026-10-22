import torch
from pathlib import Path

import numpy as np
from typing import Dict, List, Tuple

NUM_LABELS = 3  # Assuming 3 classes for classification

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

MAX_DATEID = 6554 # include this dateID

# select * from '..\parquet\dateID.parquet' where TradeDate in [cast('2015-01-05' as DATE), cast('2025-12-30' as DATE)];
# ┌───────┬────────────┬────────┬───────┬───────┐
# │ tfID  │ TradeDate  │ dateID │ train │ eval  │
# │ int64 │    date    │ int64  │ int32 │ int32 │
# ├───────┼────────────┼────────┼───────┼───────┤
# │  1634 │ 2015-01-05 │   2435 │     1 │     0 │
# │  4321 │ 2025-12-30 │   6447 │     0 │     1 │
# └───────┴────────────┴────────┴───────┴───────┘
USE_MIN_TFID = 1634 # means 2015-01-05
USE_MAX_TFID = 4321 # means 2025-12-30

PARQUET_DISR = Path("db/parquet")

CORR_EDGE_INFO_PATH = Path("scripts/datap/graph/processed/corr_edge_info.pt")


# address: 0 is center (*_i), 1 is neighbor (*_j)
HETERO_EDGE_DICT: Dict[str, Tuple[str, str]] = {
    "corr"          : ('stock' , 'stock'),
    "made_up_Mkt"   : ('stock' , 'mktIdx'),
    "made_up_topix" : ('stock' , 'mktIdx'),
    "made_up_s33"   : ('stock' , 'mktIdx'),
    "made_up_s17"   : ('stock' , 'mktIdx'),
    "recent_report" : ('stock' , 'statement'),
    "index_future"  : ('mktIdx', 'future')
}

HETERO_NODE_TYPES: List[str] = [
    'stock',
    'statement',
    'mktIdx',
    'future'
]

HETERO_EDGE_ID: Dict[str, int] = {
    "corr"          : 0,
    "made_up_Mkt"   : 1,
    "made_up_topix" : 2,
    "made_up_s33"   : 3,
    "made_up_s17"   : 4,
    "recent_report" : 5,
    "index_future"  : 6
}

HETERO_NODE_ID: Dict[str, int] = {
    "stock"        : 0,
    "statement"    : 1,
    "mktIdx"       : 2,
    "future"       : 3 
}

# select count(*)-4 as num_cols from (describe '.\*\*.parquet');
# "4" means "tfID", "codeID", "dateID", "nodeID" columns
NODE_TYPE_CFG: Dict[str, int] = {
    "stock"        : 16,
    "statement"    : 60,
    "mktIdx"       : 4,
    "future"       : 16
}

# <duckdb side processing>
# dateID is limited to 6554 (SQL: ... where dateID < 6555)
# if "ri" is nan or inf, replace it with 0.0 (SQL ... set ri=if(isnan(ri) or isinf(ri) or ri is NULL, 0, ri))
CAPM_DATA_FILE_ALIAS = "capm_data"

# alias for mapping parquet files
DATE_ID_FILE_ALIAS = "dateID"
NODE_ID_FILE_ALIAS = "nodeID"

# alias for other parquet files
RETURN_FILE_ALIAS = "returns"

# indices for processed .pt files
CORR_EDGE_INFO_INDEX = 0
PROCESSED_MARKET_DATA_INDEX = 1

# dateID.parquet
D_TFID_INDEX = 0
D_DATEID_INDEX = 1

# nodeID.parquet
N_TFID_COL_ID = 0
N_DATEID_COL_ID = 1
N_CODEID_COL_ID = 2
N_NODEID_COL_ID = 3
N_NUMOCCUR_COL_ID = 4

# other *.parquet
O_TFID_COL_ID = 0
O_DATEID_COL_ID = 1
O_CODEID_COL_ID = 2
O_NODEID_COL_ID = 3
O_MAINDATA_START_ID = 4

# window size difinition
GRU_WINDOW_SIZE = 25
NUM_OCCUR_WINDOW_SIZE = 12

# capm correlation calculation config
DEFAULT_WINDOW_SIZE = GRU_WINDOW_SIZE  # Default window size for rolling regression
CORR_THRESHOLD = 0.5  # Default threshold for correlation filtering
EDGE_TYPE = 'corr'
JENSEN_ALPHA = 'const'
BETA = 0

START_IDX = 0
END_IDX = 1
# reference: duckdb side processing
TRAIN_RANGE_BY_DATEID = (1334, 5351) # (2015-01-05, 2022-12-30)
VALID_RANGE_BY_DATEID = (5356, 5715) # (2023-01-04, 2023-12-29)
EVAL_RANGE_BY_DATEID  = (5721, 6447) # (2024-01-04, 2025-12-30)

# select * from '..\parquet\dateID.parquet' where dateID in [2435, 5351, 5356, 5715, 5721, 6447] order by tfID;
# ┌───────┬────────────┬────────┬───────┬───────┐
# │ tfID  │ TradeDate  │ dateID │ train │ eval  │
# │ int64 │    date    │ int64  │ int32 │ int32 │
# ├───────┼────────────┼────────┼───────┼───────┤
# │  1634 │ 2015-01-05 │   2435 │     1 │     0 │
# │  3587 │ 2022-12-30 │   5351 │     1 │     0 │
# │  3588 │ 2023-01-04 │   5356 │     1 │     0 │
# │  3833 │ 2023-12-29 │   5715 │     1 │     0 │
# │  3834 │ 2024-01-04 │   5721 │     1 │     0 │
# │  4321 │ 2025-12-30 │   6447 │     0 │     1 │
# └───────┴────────────┴────────┴───────┴───────┘
TRAIN_RANGE_BY_TFID = (1634, 3587) # (2015-01-05, 2022-12-30)
VALID_RANGE_BY_TFID = (3588, 3833) # (2023-01-04, 2023-12-29)
EVAL_RANGE_BY_TFID  = (3834, 4321) # (2024-01-04, 2025-12-30)
TRAIN_LENGTH = TRAIN_RANGE_BY_TFID[1] - TRAIN_RANGE_BY_TFID[0] + 1
VALID_LENGTH = VALID_RANGE_BY_TFID[1] - VALID_RANGE_BY_TFID[0] + 1
EVAL_LENGTH  = EVAL_RANGE_BY_TFID[1]  - EVAL_RANGE_BY_TFID[0]  + 1

# feature type definition
NP_FLOAT32 = np.float32
NP_INT32 = np.int32
TORCH_FLOAT32 = torch.float32
TORCH_INT32 = torch.int32
TORCH_LONG = torch.long