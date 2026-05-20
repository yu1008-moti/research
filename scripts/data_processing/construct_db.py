import pandas as pd
import numpy as np
from pathlib import Path
from typing import Tuple, List, Dict, Iterator
import sqlite3

class HomogenousConstructor:
    def __init__(self, nparray_dir: Path, financial_data_dir: Path):
        self.nparray_dir = nparray_dir
        self.financial_data_dir = financial_data_dir
        self.homogenous_df: pd.DataFrame = pd.DataFrame()
        self.daily_dirs = [d for d in self.financial_data_dir.iterdir() if d.is_dir()]


    def iter_get_pathes(self) -> Iterator[Tuple[Path, Path]]:
        for i, dir in enumerate(self.daily_dirs, start=1):
            files = {f.stem:f for f in dir.iterdir() if f.suffix == ".csv"}
            equities_bars_daily = files["equities_bars_daily"]
            equities_master = files["equities_master"]
            print(f"\r Processed {equities_bars_daily} and {equities_master}, {str(i).rjust(4)}/{len(self.daily_dirs)}", end="  ")
            yield (equities_bars_daily, equities_master)
        return
    

    def column_type_change(self):
        self.homogenous_df["Date"] = pd.to_datetime(self.homogenous_df["Date"])
        self.homogenous_df["Code"] = self.homogenous_df["Code"].astype(str)
        return 


    def build_db(self, db_name: str = "homogenous_data.db"):
        conn = sqlite3.connect(f"db/{db_name}")
        self.homogenous_df.to_sql(f"db/{db_name}", conn, if_exists="replace", index=False)
        conn.close()
        print(f"Database {db_name} created successfully.")
        return 

    def start_build(self, db_name: str):
        store_df:List[pd.DataFrame] = []
        for equities_bars_daily, equities_master in self.iter_get_pathes():
            df_bars, df_master = pd.read_csv(equities_bars_daily), pd.read_csv(equities_master)
            concat_df = df_master.merge(df_bars, on=["Date", "Code"], suffixes=("_master", "_bars"))
            store_df.append(concat_df)
        self.homogenous_df = pd.concat(store_df, ignore_index=True)
        self.column_type_change()
        self.build_db(db_name)
        return