import torch
from pathlib import Path
import numpy as np
from typing import Dict, List, Tuple
from string import Template

DB_VERSION = "r8_Nov4v"

NUM_LABELS = 3  # Assuming 3 classes for classification

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# MAX_TID = 4392 # include this dateID

# USE_MIN_TFID = 1634 # means 2015-01-05
# USE_MAX_TFID = 4321 # means 2025-12-30

PARQUET_DISR = Path("db/parquet")

CAPM_DATA_FILE_PATH = Path("scripts/datap/graph/processed/capm_data.parquet")
CORR_EDGE_INFO_PATH = Path("scripts/datap/graph/processed/corr_edge_info.npz")


HETERO_EDGE_UNIT: Dict[str, Tuple[str, str]] = {
    # r: (src_ntNm, tgt_ntNm)
    "corr"           : ("stock"     , "stock"),
    "recent_report"  : ("statement" , "stock"),
    "made_up_mkt"    : ("mktidx"    , "stock"),
    "made_up_topix"  : ("mktidx"    , "stock"),
    "made_up_s17"    : ("mktidx"    , "stock"),
    "mktidx_future"  : ("future"    , "mktidx")
}

HETERO_NODE_TYPES: List[str] = [
    'stock',
    'statement',
    'mktidx',
    'future'
]


HETERO_EDGE_TYPES: List[str] = [
    'corr',
    'recent_report',
    'made_up_mkt',
    'made_up_topix',
    'made_up_s17',
    'mktidx_future'
]

HETERO_EDGE_UNIT_ID: List[Tuple[int, int, int]] = [
    # (i, j, r) = (source_node_type_id, target_node_type_id, edge_type_id)
    (0, 0, 0),  # corr: stock -> stock
    (1, 0, 1),  # recent_report: statement -> stock
    (2, 0, 2),  # made_up_mkt: mktidx -> stock
    (2, 0, 3),  # made_up_topix: mktidx -> stock
    (2, 0, 4),  # made_up_s17: mktidx -> stock
    (3, 2, 5)   # mktidx_future: mktidx -> future
]

HETERO_NODE_ID: Dict[str, int] = {
    'stock'    : 0,
    'statement': 1,
    'mktidx'   : 2,
    'future'   : 3
}

HETERO_EDGE_ID: Dict[str, int] = {
    'corr'           : 0,
    'recent_report'  : 1,
    'made_up_mkt'    : 2,
    'made_up_topix'  : 3,
    'made_up_s17'    : 4,
    'mktidx_future'  : 5
}


# select count(*)-4 as num_cols from (describe '.\*\*.parquet');
# "4" means "tfID", "codeID", "dateID", "nodeID" columns
NODE_TYPE_INPUT_NUM: Dict[str, int] = {
    "stock"        : 5,
    "statement"    : 19,
    "mktidx"       : 4,
    "future"       : 6
}

# 0: tID, 1: elpDs, 2: gnID, 3: lnID, 4: cID, 5:ntID, 6~ : feats
NODE_FEATS_HEAD_IDX = 6

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
O_TID_COL_ID = 0
O_DATEID_COL_ID = 1
O_CODEID_COL_ID = 2
O_NODEID_COL_ID = 3
O_MAINDATA_START_ID = 4

ND = {
    "stock"    : {"O": 0, "H": 1, "L": 2, "C": 3, "V": 4},
    "statement": {"Sales": 0, "OP": 1, "OdP": 2, "NP": 3, "EPS": 4, "TA": 5, "Eq": 6, "EqAR": 7, "BPS": 8, "CFO": 9, "CFI": 10, "CFF": 11, "CashEq": 12, "DivnQ": 13, "ActualShOutFY": 14},
    "mktidx"   : {"O": 0, "H": 1, "L": 2, "C": 3},
    "future"   : {"O": 0, "H": 1, "L": 2, "C": 3, "V": 4, "OI": 5},
}

# window size difinition
GRU_WINDOW_SIZE = 25
NUM_OCCUR_WINDOW_SIZE = 12

# capm correlation calculation config
DEFAULT_WINDOW_SIZE = GRU_WINDOW_SIZE  # Default window size for rolling regression
CORR_THRESHOLD = 0.9 # Default threshold for correlation filtering
EDGE_TYPE = 'corr'
JENSEN_ALPHA = 'const'
BETA = 'Rm'

START_idX = 0
END_idX = 1

TRAIN_RANGE_TID = (1634, 3587) # (2015-01-05, 2022-12-30)
VALID_RANGE_TID = (3588, 3833) # (2023-01-04, 2023-12-29)
EVAL_RANGE_TID  = (3834, 4321) # (2024-01-04, 2025-12-30)

# TRAIN_RANGE_TID = (2856, 2934) # (2020-01-06, 2020-04-30)
# VALID_RANGE_TID = (2953, 2974) # (2020-06-01, 2020-06-30)
# EVAL_RANGE_TID  = (2975, 2995) # (2020-07-01, 2020-07-31)

_BASE = 1634

_TID_SPLIT = [
    (1634 - _BASE, 1877 - _BASE), # 2015-01-05, 2015-12-30
    (1878 - _BASE, 2122 - _BASE), # 2016-01-04, 2016-12-30
    (2123 - _BASE, 2369 - _BASE), # 2017-01-04, 2017-12-29
    (2370 - _BASE, 2614 - _BASE), # 2018-01-04, 2018-12-28
    (2615 - _BASE, 2855 - _BASE), # 2019-01-04, 2019-12-30
    (2856 - _BASE, 3098 - _BASE), # 2020-01-06, 2020-12-30
    (3099 - _BASE, 3343 - _BASE), # 2021-01-04, 2021-12-30
    (3344 - _BASE, 3587 - _BASE), # 2022-01-04, 2022-12-30
]

TRAIN_SPLIT = [
    (int(_TID_SPLIT[id][0]), int(_TID_SPLIT[id][1]*0.8)) for id in range(len(_TID_SPLIT))
]

VALID_SPLIT = [
    (int(_TID_SPLIT[id][1]*0.8), _TID_SPLIT[id][1]) for id in range(len(_TID_SPLIT))
]

TEST_SPLIT = [
    (3588 - _BASE, 4078 - _BASE), # 2023-01-04, 2024-12-30
]



# TRAIN_RANGE = (0             , 0              + (TRAIN_RANGE_TID[1] - TRAIN_RANGE_TID[0] + 1))
# VALID_RANGE = (TRAIN_RANGE[1], TRAIN_RANGE[1] + (VALID_RANGE_TID[1] - VALID_RANGE_TID[0] + 1))
# EVAL_RANGE  = (VALID_RANGE[1], VALID_RANGE[1] + (EVAL_RANGE_TID[1]  - EVAL_RANGE_TID[0]  + 1))

USE_MIN_TID = TRAIN_RANGE_TID[0]
USE_MAX_TID = EVAL_RANGE_TID[1]

# feature type definition
NP_FLOAT32 = np.float32
NP_INT32 = np.int32
TORCH_FLOAT32 = torch.float32
TORCH_INT32 = torch.int32
TORCH_LONG = torch.long

ACT_DB_PATH = Path(f"./db/synthesis/{DB_VERSION}/{DB_VERSION}.act.duckdb")
DEV_DB_PATH = Path(f"./db/synthesis/{DB_VERSION}/{DB_VERSION}.dev.duckdb")

GET_TID_QUERY = \
f"""\
select tID \
from act.tools.date_tool \
where tID between {USE_MIN_TID} and {USE_MAX_TID} \
order by tID;\
"""

GET_NODE_DATA_MASTER_QUERY = Template(
"""
select *
from act.nodes.${ntNm}
order by tID, gnID;
"""
)

SET_EDGES_QUERY = Template(
"""
select ${src_ntNm}_lnID, ${tgt_ntNm}_lnID
from act.edges.${etNm}
where tID = ${tID}
order by ${src_ntNm}_gnID, ${tgt_ntNm}_gnID;
"""
)

SET_NODES_QUERY = Template( 
"""
select gnID, ntID, seq, seq_len
from act.seq.node
where
(ntID=0 and tID=${tID})
or
(ntID=1 and tID<=${tID})
or
(ntID=2 and tID=${tID})
or
(ntID=3 and tID=${tID})
order by gnID;
"""
)
