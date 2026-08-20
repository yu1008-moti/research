import pandas as pd
from string import Template
import duckdb as db
from scripts.datap.graph.cons import related_fetch as cf
from scripts.datap.graph.cons import train_constants as ct

class fetch:

    @staticmethod
    def _any(QUERY:str) -> pd.DataFrame:
        conn = db.connect(cf.PATH_DB)
        result = conn.execute(QUERY).df()
        conn.close()
        return result

    # SQL QUERY TO FETCH DATA OF PRICES
    @staticmethod
    def prices() -> pd.DataFrame:
        with open(cf.PATH_SQL_TO_FETCH_PRICES, "r") as f:
            EQUITY_FETCH_QUERY = Template(f.read()).substitute(
                    YEAR_START=cf.YEAR_START*100, 
                    YEAR_END=(cf.YEAR_END+1)*100
                )
        return fetch._any(EQUITY_FETCH_QUERY)

    # SQL QUERY TO FETCH FINANCIAL DATA
    @staticmethod
    def financials(registered_nodes: list) -> pd.DataFrame:
        with open(cf.PATH_SQL_TO_FETCH_FINANCIALS, "r") as f:
            FINANCIAL_STATEMENTS_FETCH_QUERY = Template(f.read()).substitute(
                    REGISTERED_CODES=registered_nodes
                )
        return fetch._any(FINANCIAL_STATEMENTS_FETCH_QUERY)
