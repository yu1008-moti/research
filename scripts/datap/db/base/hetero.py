import pandas as pd
import os
from abc import ABC, abstractmethod
from scratch import FromScratchDBConstructor
from typing import List, Iterator
from pathlib import Path

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
            if os.path.getsize(p) < 3:
                continue
            self._processing_msg(p, i, self.daily_dirs)
            yield p
        return
    

    def start_build(self):
        store_df:List[pd.DataFrame] = []
        for p in self.iter_get_path():
            df = pd.read_csv(p)
            df = df.replace(r"^\-$", float("nan"), regex=True)
            df = df.replace(r"^\*$", float("nan"), regex=True)
            store_df.append(df)
        self.build_db(store_df)
        self.start_convert()
        return