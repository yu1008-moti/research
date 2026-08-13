import duckdb as db
import pandas as pd
from pathlib import Path
from string import Template

PATH_TO_DATABASE = "db/synthesis/synthesis.duckdb"
TABLE_NAME = "imp.eqt_main"

class Templates:

    @property
    def isedge(self):
        return Template(
            f"""
            WITH target AS (
            SELECT '$TradeDate'::DATE AS trade_date
            ),
            recent AS (
            SELECT
                Code, TradeDate, DAdjC,
                ROW_NUMBER() OVER (PARTITION BY Code ORDER BY TradeDate DESC) AS rn_desc
            FROM {TABLE_NAME}
            WHERE TradeDate <= (SELECT trade_date FROM target)
            QUALIFY rn_desc <= $window_size
            ),
            per_code AS (
            SELECT
                Code,
                COUNT(*) AS n,
                LIST(DAdjC ORDER BY TradeDate) AS px
            FROM recent
            GROUP BY Code
            HAVING MAX(TradeDate) = (SELECT trade_date FROM target) 
            ),
            pairs AS (
            SELECT
                a.Code AS t1_Code,
                b.Code AS t2_Code,
                LEAST(a.n, b.n) AS k,
                list_slice(a.px, -LEAST(a.n, b.n), -1) AS xa,
                list_slice(b.px, -LEAST(a.n, b.n), -1) AS xb
            FROM per_code a
            -- JOIN per_code b ON a.Code <= b.Code /* with self-loop */
            JOIN per_code b ON a.Code < b.Code /* without self-loop */
            ),
            demeaned AS (
            SELECT
                t1_Code, t2_Code, k,
                list_transform(xa, v -> v - list_avg(xa)) AS dxa,
                list_transform(xb, v -> v - list_avg(xb)) AS dxb
            FROM pairs
            ),
            raw_corr AS(
            SELECT
                (SELECT trade_date FROM target) AS TradeDate,
                t1_Code, t2_Code, k,
                list_dot_product(dxa, dxb)
                / NULLIF(
                    SQRT(
                        GREATEST(list_dot_product(dxa, dxa), 0) *
                        GREATEST(list_dot_product(dxb, dxb), 0)
                    ), 0
                    ) AS c
            FROM demeaned
            )
            SELECT
                TradeDate AS snapshot_id, 
                t1_Code AS src_node_id, 
                t2_Code AS dst_node_id, 
                IF(ABS(c) > $threshold, 1, 0) AS _c
            FROM raw_corr
            WHERE _c = 1
            """
        )

    @property
    def get_Codes_by_TradeDate(self):
        return Template(
            f"""
            SELECT 
                TradeDate, 
                Code,
                -- LIST OF FEATURES
            FROM {TABLE_NAME}
            WHERE TradeDate = '$TradeDate'
            """
        )

    @property
    def get_TradeDates(self):
        return Template(
            f"""
            SELECT DISTINCT TradeDate
            FROM {TABLE_NAME}
            ORDER BY TradeDate
            """
        )

    @property
    def insert_edge_data(self):
        return Template(
            f"""
            INSERT INTO graph.edge SELECT * FROM df
            """
        )

def _send_select_query(query: str, query_type: str = "select") -> pd.DataFrame:
    with db.connect(PATH_TO_DATABASE) as con:
        resp = con.sql(query).df()
    return resp

def _send_insert_query(query: str, df: pd.DataFrame, query_type: str = "insert") -> None:
    with db.connect(PATH_TO_DATABASE) as con:
        con.register("df", df)
        con.sql(query)
    return

def _register_edges():
    TMPs = Templates()
    TradeDateList = _send_select_query(TMPs.get_TradeDates.substitute())
    for TradeDate in TradeDateList["TradeDate"].dt.strftime('%Y-%m-%d'): #[100:101]:  # Process only the first 5 dates for testing
        print(f"Processing TradeDate: {TradeDate}")
        query = TMPs.isedge.substitute(
            TradeDate=TradeDate,
            window_size=75,
            threshold=0.9
        )
        print("Computing edges...")
        df = _send_select_query(query)
        query = TMPs.insert_edge_data.substitute()
        print("Inserting edges into the database...")
        _send_insert_query(query, df=df)
        print(f"-- Edges for TradeDate {TradeDate} inserted successfully. --")
    return

def _register_nodes():
    TMPs = Templates()
    TradeDateList = _send_select_query(TMPs.get_TradeDates.substitute())
    for TradeDate in TradeDateList["TradeDate"].dt.strftime('%Y-%m-%d'): #[100:101]:  # Process only the first 5 dates for testing
        print(f"Processing TradeDate: {TradeDate}")
        query = TMPs.get_Codes_by_TradeDate.substitute(
            TradeDate=TradeDate,
        )
        print("Computing nodes...")
        df = _send_select_query(query)
        query = f"INSERT INTO graph.node SELECT * FROM df"
        print("Inserting nodes into the database...")
        _send_insert_query(query, df=df)
        print(f"-- Nodes for TradeDate {TradeDate} inserted successfully. --")
    return