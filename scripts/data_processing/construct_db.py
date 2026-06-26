import pandas as pd
from pathlib import Path
from typing import Tuple, List, Iterator
import sqlite3
from scripts.constant import paths, msg
from abc import ABC, abstractmethod


__all__ = ["prc_DBConstructor", "drv_DBConstructor"]


class DBConstructor(ABC):
    def __init__(self, symbol: str, table_name: str):
        PATHS, self.MSG = paths(), msg()

        self.CSVDATA_STORE_DIR = PATHS.CSVDATA_STORE_DIR

        self.symbol = symbol
        self.db_path = PATHS.DB_STORE_DIR / f"{symbol}.sqlite3"
        self.table_name = table_name

        self.df: pd.DataFrame = pd.DataFrame()

        self.daily_dirs = [d for d in self.CSVDATA_STORE_DIR.iterdir() if d.is_dir()]

        print(
            f"target symbol : {self.symbol}\n",            
            f"  - save db : {self.db_path}\n",
            f"  - table name : {self.table_name}\n",
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
        conn = sqlite3.connect(self.db_path)
        self.df.to_sql(self.table_name, conn, if_exists="replace", index=False)
        conn.close()
        print(self.MSG.build_db_end)
        return 

    @abstractmethod
    def start_build(self):
        pass


class HomoDBConstructor(DBConstructor, ABC):
    def __init__(self, symbols: List[str], table_name: str):
        super().__init__(symbols[0], table_name)
        self.symbol_bars, self.symbol_mstr = symbols
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
        return


class HeteroDBConstructor(DBConstructor, ABC):
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