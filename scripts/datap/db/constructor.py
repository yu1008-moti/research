from base.homo import HomoDBConstructor
from base.hetero import HeteroDBConstructor
from typing import List

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


class inv_DBConstructor(HeteroDBConstructor):
    def __init__(self, symbol:str, table_name:str):
        super().__init__(symbol=symbol, table_name=table_name)


    def start_build(self):
        super().start_build()


class idx_DBConstructor(HeteroDBConstructor):
    def __init__(self, symbol:str, table_name:str):
        super().__init__(symbol=symbol, table_name=table_name)


    def start_build(self):
        super().start_build()


class mbd_DBConstructor(HeteroDBConstructor):
    def __init__(self, symbol:str, table_name:str):
        super().__init__(symbol=symbol, table_name=table_name)


    def start_build(self):
        super().start_build()


class fin_DBConstructor(HeteroDBConstructor):
    def __init__(self, symbol:str, table_name:str):
        super().__init__(symbol=symbol, table_name=table_name)


    def start_build(self):
        super().start_build()