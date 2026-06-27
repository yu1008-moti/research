from scripts.data_processing.construct_db import *
from typing import List

def build_prc_db(symbols: List[str], table_name:str):
    constructer = prc_DBConstructor(symbols, table_name)
    constructer.start_build()

def build_drv_db(symbol:str, table_name:str):
    constructer = drv_DBConstructor(symbol, table_name)
    constructer.start_build()

def sqlite2duckdb(symbol: str, table_name: str):
    converter = duckDBConverter(symbol, table_name)
    converter.start_convert()