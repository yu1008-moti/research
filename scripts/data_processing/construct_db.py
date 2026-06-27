import pandas as pd
from pathlib import Path
from typing import Tuple, List, Iterator
import sqlite3
from scripts.constant import paths, msg, nums, cvt_sql, bld_sql
from abc import ABC, abstractmethod
import duckdb  as dkdb
import sqlite3 as sql3
import os


__all__ = ["prc_DBConstructor", "drv_DBConstructor", "duckDBConverter"]


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


class FromScratchDBConstructor(ABC):
    def __init__(self, symbol: str, table_name: str):
        PATHS, self.MSG = paths(), msg()

        self.CSVDATA_STORE_DIR = PATHS.CSVDATA_STORE_DIR

        self.symbol = symbol
        self.sqlite3_path = PATHS.SQLITE_STORE_DIR / f"{symbol}.db"
        self.duckdb_path  = PATHS.DUCKDB_STORE_DIR / f"{symbol}.duckdb"

        self.table_name = table_name

        self.df: pd.DataFrame = pd.DataFrame()

        self.daily_dirs = [d for d in self.CSVDATA_STORE_DIR.iterdir() if d.is_dir()]

        exists_sqlite = self.sqlite3_path.exists()
        exists_duckdb = self.duckdb_path.exists()

        print(
            f"target symbol : {self.symbol}\n",            
            f"  - save db     : {self.sqlite3_path} {'[exists]' if exists_sqlite else '[not found]'}\n",
            f"  - table name  : {self.table_name} {'[exists]' if exists_duckdb else '[not found]'}\n",
            # f"  - save duckdb : {self.duckdb_path}\n"
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
        self.df["Date"] = pd.to_datetime(self.df["Date"])
        self.df["Code"] = self.df["Code"].astype(str)
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
        dkdb_cvt = duckDBConverter(self.symbol, self.table_name)
        if bld_sql().is_cvt:
            print("denied: cannot convert database while building it.")
        else:
            dkdb_cvt.start_convert()
        return

    @abstractmethod
    def start_build(self):
        pass


class HomoDBConstructor(FromScratchDBConstructor, ABC):
    def __init__(self, symbols: List[str], table_name: str):
        super().__init__(symbols[0], table_name)
        self.symbol_mstr, self.symbol_bars = symbols
        pass


    def _processing_msg(self, p:Tuple[Path, Path], i: int, daily_dirs: List[Path]):
        ratio:str = str(i).rjust(4) + "/" + str(len(daily_dirs)).rjust(4)
        return print(f"\r Processed {p[0]} and {p[1]}, {ratio}", end="  ")


    def iter_get_path(self) -> Iterator[Tuple[Path, Path]]:
        for i, dir in enumerate(self.daily_dirs, start=1):
            p_dict = {f.stem:f for f in dir.iterdir() if f.suffix == ".csv"}
            p = (p_dict[self.symbol_bars], p_dict[self.symbol_mstr])
            self._processing_msg(p, i, self.daily_dirs)
            yield p
        return
        

    def start_build(self):
        store_df:List[pd.DataFrame] = []
        for p_bars, p_mstr in self.iter_get_path():
            df_bars, df_master = pd.read_csv(p_bars), pd.read_csv(p_mstr)
            concat_df = df_master.merge(df_bars, on=["Date", "Code"])
            store_df.append(concat_df)
        self.build_db(store_df)
        self.start_convert()
        return


class HeteroDBConstructor(FromScratchDBConstructor, ABC):
    def __init__(self, symbol: str, table_name: str):
        super().__init__(symbol, table_name)
        return
    

    def _processing_msg(self, p: Path, i: int, daily_dirs: List[Path]):
        ratio:str = str(i).rjust(4) + "/" + str(len(daily_dirs)).rjust(4)
        return print(f"\r Processed {p}, {ratio}", end="  ")
    

    def iter_get_path(self) -> Iterator[Path]:
        for i, dir in enumerate(self.daily_dirs, start=1):
            p_dict = {f.stem:f for f in dir.iterdir() if f.suffix == ".csv"}
            p = p_dict[self.symbol]
            self._processing_msg(p, i, self.daily_dirs)
            yield p
        return
    

    def start_build(self):
        store_df:List[pd.DataFrame] = []
        for p in self.iter_get_path():
            df = pd.read_csv(p)
            store_df.append(df)
        self.build_db(store_df)
        self.start_convert()
        return


class prc_DBConstructor(HomoDBConstructor):
    def __init__(self, symbols: List[str], table_name:str):
        super().__init__(symbols, table_name)
    

    def start_build(self):
        super().start_build()
    

class drv_DBConstructor(HeteroDBConstructor):
    def __init__(self, symbol:str, table_name:str):
        super().__init__(symbol=symbol, table_name=table_name)


    def start_build(self):
        super().start_build()

