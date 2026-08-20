import pandas as pd
from abc import ABC, abstractmethod
from scratch import FromScratchDBConstructor
from pathlib import Path
from typing import List, Iterator, Tuple

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