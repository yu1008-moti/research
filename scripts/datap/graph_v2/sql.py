import pandas as pd
from string import Template
import duckdb as db
from scripts.datap.graph_v2.cons import related_fetch as cf


class fetch:

    @staticmethod
    def _any(QUERY: str) -> pd.DataFrame:
        conn = db.connect(cf.PATH_DB)
        result = conn.execute(QUERY).df()
        conn.close()
        return result

    # SQL QUERY TO FETCH DATA OF PRICES
    @staticmethod
    def prices() -> pd.DataFrame:
        with open(cf.PATH_SQL_TO_FETCH_PRICES, "r", encoding="utf-8") as f:
            # week_id の範囲は SQL 側にハードコードしてあるので置換は任意
            EQUITY_FETCH_QUERY = Template(f.read()).safe_substitute()
        return fetch._any(EQUITY_FETCH_QUERY)

    # SQL QUERY TO FETCH FINANCIAL DATA
    @staticmethod
    def financials() -> pd.DataFrame:
        with open(cf.PATH_SQL_TO_FETCH_FINANCIALS, "r", encoding="utf-8") as f:
            FINANCIAL_STATEMENTS_FETCH_QUERY = Template(f.read()).safe_substitute()
        return fetch._any(FINANCIAL_STATEMENTS_FETCH_QUERY)
