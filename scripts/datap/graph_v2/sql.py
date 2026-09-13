import pandas as pd
from string import Template
import duckdb as db
from scripts.datap.graph_v2.cons import rel_sql as cf


class fetch:

    @staticmethod
    def _any(QUERY: str, DB_NAME: str) -> pd.DataFrame:
        conn = db.connect(DB_NAME)
        result = conn.execute(QUERY).df()
        conn.close()
        return result

    # SQL QUERY TO FETCH DATA OF PRICES
    @staticmethod
    def prices() -> pd.DataFrame:
        with open(cf.PATH_SQL_TO_FETCH_PRICES, "r", encoding="utf-8") as f:
            # week_id の範囲は SQL 側にハードコードしてあるので置換は任意
            EQUITY_FETCH_QUERY = Template(f.read()).safe_substitute(
                START_WEEK_ID=cf.START_WEEK_ID,
                END_WEEK_ID=cf.END_WEEK_ID
            )
        return fetch._any(EQUITY_FETCH_QUERY, cf.PATH_ORIGINAL_DB)

    # SQL QUERY TO FETCH FINANCIAL DATA
    @staticmethod
    def financials() -> pd.DataFrame:
        with open(cf.PATH_SQL_TO_FETCH_FINANCIALS, "r", encoding="utf-8") as f:
            FINANCIAL_STATEMENTS_FETCH_QUERY = Template(f.read()).safe_substitute(
                START_WEEK_ID=cf.START_WEEK_ID,
                END_WEEK_ID=cf.END_WEEK_ID
            )
        return fetch._any(FINANCIAL_STATEMENTS_FETCH_QUERY, cf.PATH_ORIGINAL_DB)


    # TO DATASET [edge]
    @staticmethod
    def edge_index(serial_id: int) -> pd.DataFrame:
        QUERY = f"SELECT src_node_id, dst_node_id FROM edge"
        DB_NAME = cf.PATH_GRAPHINFO_DB.safe_substitute(serial_id=serial_id)
        return fetch._any(QUERY, DB_NAME)

    @staticmethod
    def edge_attr(serial_id: int, attr_name: str) -> pd.DataFrame:
        QUERY = f"SELECT {attr_name} FROM edge"
        DB_NAME = cf.PATH_GRAPHINFO_DB.safe_substitute(serial_id=serial_id)
        return fetch._any(QUERY, DB_NAME)

    # TO DATASET [node]
    @staticmethod
    def node_attr(serial_id: int, attr_name: str) -> pd.DataFrame:
        QUERY = f"SELECT {attr_name} FROM node"
        DB_NAME = cf.PATH_GRAPHINFO_DB.safe_substitute(serial_id=serial_id)
        return fetch._any(QUERY, DB_NAME)
    
    @staticmethod
    def node_table(serial_id: int, node_type: str) -> pd.DataFrame:
        QUERY = f"SELECT n.*, f.feats FROM node n JOIN feats f ON n.node_id = f.node_id WHERE n.node_type = '{node_type}'"
        DB_NAME = cf.PATH_GRAPHINFO_DB.safe_substitute(serial_id=serial_id)
        return fetch._any(QUERY, DB_NAME)

class insert:

    @staticmethod
    def _any(QUERY: str, data_list: pd.DataFrame, serial_id: int) -> None:
        conn = db.connect(cf.PATH_GRAPHINFO_DB.safe_substitute(serial_id=serial_id))
        conn.execute(QUERY)
        conn.close()

    @staticmethod
    def edge(data_list: pd.DataFrame, serial_id: int) -> None:
        with open(cf.PATH_SQL_TO_INSERT_TO_EDGE_TABLE, "r", encoding="utf-8") as f:
            INSERT_QUERY = Template(f.read()).safe_substitute()
        insert._any(INSERT_QUERY, data_list, serial_id)

    @staticmethod
    def node(data_list: pd.DataFrame, serial_id: int) -> None:
        with open(cf.PATH_SQL_TO_INSERT_TO_NODE_TABLE, "r", encoding="utf-8") as f:
            INSERT_QUERY = Template(f.read()).safe_substitute()
        insert._any(INSERT_QUERY, data_list, serial_id)

    @staticmethod
    def feats(data_list: pd.DataFrame, serial_id: int) -> None:
        with open(cf.PATH_SQL_TO_INSERT_TO_FEATS_TABLE, "r", encoding="utf-8") as f:
            INSERT_QUERY = Template(f.read()).safe_substitute()
        insert._any(INSERT_QUERY, data_list, serial_id)


class create:

    @staticmethod
    def graph_info(serial_id: int) -> None:
        conn = db.connect(cf.PATH_GRAPHINFO_DB.safe_substitute(serial_id=serial_id))
        with open(cf.PATH_SQL_TO_CREATE_GRAPHINFO_TABLE, "r", encoding="utf-8") as f:
            CREATE_QUERY = Template(f.read()).safe_substitute()
        conn.execute(CREATE_QUERY)
        conn.close()
