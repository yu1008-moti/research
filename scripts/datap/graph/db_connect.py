import duckdb as db
import pandas as pd
from pathlib import Path
from string import Template

PATH_TO_ORIGIN_DB = Path("./db/synthesis/synthesis.duckdb")
START_WEEK_ID = 200819
END_WEEK_ID = 202616


def get_main_price_table() -> pd.DataFrame:

    PATH_TO_SQL = Path('./sql/graph/get_table_to_CAPM.sql')

    query = None

    with open(PATH_TO_SQL, 'r', encoding='utf-8') as f:
        query = Template(f.read()).substitute(START_WEEK_ID=START_WEEK_ID, END_WEEK_ID=END_WEEK_ID)

    assert isinstance(query, str), "SQL query is None"

    conn = db.connect(database=PATH_TO_ORIGIN_DB, read_only=True)
    df = conn.execute(query=query).df()

    conn.close()

    print("======== get_main_price_table() ========")
    print("rows:", len(df))
    print("columns:", df.columns.tolist())
    print(df.head(5))
    print("========================================")

    return df