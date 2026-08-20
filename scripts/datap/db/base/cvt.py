import pandas as pd
from scripts.datap.db.cons import *
import os
import duckdb as dkdb
import sqlite3 as sql3


class duckDBConverter():
    def __init__(self, symbol:str, table_name:str):
        NUMS = nums()
        PATHS = paths()
        self.SQL = cvt_sql(symbol)
        self.MSG = msg()
        
        self.SYMBOL = symbol
        self.table_name = table_name
        self.chunk_size, self.offset = NUMS.DUCKDB_CVT_CFG

        self.sqlite_path = PATHS.SQLITE_STORE_DIR / f"{self.SYMBOL}.db"
        self.duckdb_path = PATHS.DUCKDB_STORE_DIR / f"{self.SYMBOL}.duckdb"

        sqlite_path_exists = self.sqlite_path.exists()
        duckdb_path_exists = self.duckdb_path.exists()

        print(
            f"target symbol : {self.SYMBOL}\n",
            f"  - from sqlite : {self.sqlite_path} {'[exists]' if sqlite_path_exists else '[not found]'}\n",
            f"  + to duckdb   : {self.duckdb_path} {'[exists]' if duckdb_path_exists else '[not found]'}\n",
            f"      - table name : {self.table_name}\n",
        )

        while wait := input(f"{self.MSG.convert_db_start} (y/n): ").lower() != "y":
            if wait:
                print("Aborted.")
                exit(0)

        return 
    

    def _open_connection(self):
        self.duckdb_con = dkdb.connect(database=self.duckdb_path)
        self.sqlite_con = sql3.connect(database=self.sqlite_path)
        return None 
    

    def _add_offset(self):
        self.offset += self.chunk_size
        return None
    

    def _close_connection(self):
        self.duckdb_con.close()
        self.sqlite_con.close()
        return None


    def _iter_change_coltypes(self, df: pd.DataFrame):
        for datelike_col in self.SQL.Datelike_cols:
            df[datelike_col] = pd.to_datetime(df[datelike_col])
        
        for text_col in self.SQL.Text_cols:
            df[text_col] = df[text_col].astype(str)

        return df
    

    def _iter_get_df(self):

        first_chunk = True

        while True:
            df = pd.read_sql(
                f"SELECT * FROM {self.table_name} LIMIT {self.chunk_size} OFFSET {self.offset}",
                self.sqlite_con
            )
            if df.empty: break
            
            df = self._iter_change_coltypes(df)
            
            if first_chunk:
                self.duckdb_con.execute(f"CREATE TABLE {self.table_name} AS SELECT * FROM df")
                first_chunk = False
            else:
                self.duckdb_con.execute(f"INSERT INTO {self.table_name} SELECT * FROM df")
            self._add_offset()

            print(f"Loaded {self.offset:,} rows...")


    def start_convert(self):
        try:
            self._open_connection()
            self._iter_get_df()
        except Exception as e:
            print(e)
            os.remove(self.duckdb_path)
            print(f"\nError occurred. Removed {self.duckdb_path}.")
        finally:
            self._close_connection()
            print(self.MSG.convert_db_end)

