import pandas as pd
from abc import ABC, abstractmethod
from scripts.datap.db.cons import paths, msg, bld_sql
import sqlite3
from base.cvt import duckDBConverter as dkdbc
from typing import List

class FromScratchDBConstructor(ABC):
    def __init__(self, symbol: str, table_name: str):
        PATHS, self.MSG, self.SQL = paths(), msg(), bld_sql(symbol)

        self.CSVDATA_STORE_DIR = PATHS.CSVDATA_STORE_DIR

        # All files contain the same content
        self.ALL_IS_SAME = self.SQL.ALL_IS_SAME

        self.symbol = symbol
        self.sqlite3_path = PATHS.SQLITE_STORE_DIR / f"{symbol}.db"
        self.duckdb_path  = PATHS.DUCKDB_STORE_DIR / f"{symbol}.duckdb"

        self.table_name = table_name

        self.df: pd.DataFrame = pd.DataFrame()

        self.daily_dirs = [d for d in self.CSVDATA_STORE_DIR.iterdir() if d.is_dir()]

        if self.ALL_IS_SAME:
            self.daily_dirs = [self.daily_dirs[-1]]

        exists_sqlite = self.sqlite3_path.exists()
        exists_duckdb = self.duckdb_path.exists()

        print(
            f"target symbol : {self.symbol}\n",            
            f"  - save db     : {self.sqlite3_path} {'[exists]' if exists_sqlite else '[not found]'}\n",
            f"  - table name  : {self.table_name} {'[exists]' if exists_duckdb else '[not found]'}\n",
            f"  - ALL SAME    : {self.ALL_IS_SAME}\n",
        )

        while wait := input(f"{self.MSG.build_db_start} (y/n): ").lower() != "y":
            if wait:
                print("Aborted.")
                exit(0)
        return 
    

    @abstractmethod
    def _processing_msg(self):
        pass


    @abstractmethod
    def iter_get_path(self):
        pass


    def column_type_change(self):
        for datelike_col in self.SQL.Datelike_cols:
            self.df[datelike_col] = pd.to_datetime(self.df[datelike_col])
        
        for text_col in self.SQL.Text_cols:
            self.df[text_col] = self.df[text_col].astype(str)
        return 
    

    def build_db(self, store_df:List[pd.DataFrame]):
        self.df = pd.concat(store_df, ignore_index=True)
        self.column_type_change()
        conn = sqlite3.connect(self.sqlite3_path)
        self.df.to_sql(self.table_name, conn, if_exists="replace", index=False)
        conn.close()
        print(self.MSG.build_db_end)
        return 
    

    def start_convert(self):
        dkdb_cvt = dkdbc(self.symbol, self.table_name)
        if self.SQL.is_cvt:
            dkdb_cvt.start_convert()
        else:
            print("denied: cannot convert database while building it.")
        return

    @abstractmethod
    def start_build(self):
        pass

