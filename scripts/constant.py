from pathlib import Path
from typing import Optional


class paths:

    @property
    def CSVDATA_STORE_DIR(self):
        return Path("data_financial")
    
    @property
    def SQLITE_STORE_DIR(self):
        return Path("db/sqlite")
    
    @property
    def DUCKDB_STORE_DIR(self):
        return Path("db/duckdb")


class msg:

    # Messages related to database building
    
    @property
    def build_db_start(self):
        return "Start building database..."


    @property
    def build_db_end(self):
        return "Database built successfully."


    @property
    def build_db_error(self):
        return "Error occurred while building the database."
    

    @property
    def path_not_found(self):
        return "No CSV file found for the specified symbol in directory: "
    

    @property
    def completed(self):
        return "Database build process completed."

    # Messages related to CLI arguments

    @property
    def invalid_db_type(self):
        return "Invalid database type specified. Please use 'price' or 'drv'."
    

    @property
    def missing_drv_flag(self):
        return "Missing flag for derivatives database. Please use '-f' for futures or '-o' for options."
    

    @property
    def invalid_drv_flag(self):
        return "Invalid flag for derivatives database. Please use '-f' for futures or '-o' for options."
    
    # Messages related to database conversion

    @property
    def convert_db_start(self):
        return "Start converting database from SQLite to DuckDB..."
    
    @property
    def convert_db_end(self):
        return "Database conversion completed successfully."
    

class doc_symbols:

    @property
    def prc_bars(self):
        return 'equities_bars_daily'
    
    @property
    def prc_mstr(self):
        return 'equities_master'

    @property
    def opt(self):
        return 'derivatives_bars_daily_options'

    @property
    def ftr(self):
        return 'derivatives_bars_daily_futures'


class tbl_names:

    @property
    def prc_tblnm(self):
        return 'eqt_main'

    @property
    def opt_tblnm(self):
        return 'drv_opt'

    @property
    def ftr_tblnm(self):
        return 'drv_ftr'
    

class nums:

    @property
    def DUCKDB_CVT_CFG(self):
        chunk_size = 500_000
        offset = 0
        return (chunk_size, offset)


### related SQL classes for building and converting databases
class sqlbase:

    def __init__(self): ...
    
    @property
    def is_cvt(self): ...
    
class cvt_sql(sqlbase):

    def __init__(self, symbol:str):
        self.symbol = symbol

    @property
    def Datelike_cols(self):
        if self.symbol == "equities_bars_daily":
            return ["Date"]
        elif self.symbol == "derivatives_bars_daily_futures":
            return ["Date", "CM", "LTD", "SQD"]
        elif self.symbol == "derivatives_bars_daily_options":
            return ["Date", "CM", "LTD", "SQD"]
        else:
            return ["Date"]
    
    @property
    def Text_cols(self):
        if self.symbol == "equities_bars_daily":
            return ["Code", "CoName", "CoNameEn", "S17Nm", "S33Nm", "ScaleCat", "MktNm", "MrgnNm"]
        elif self.symbol == "derivatives_bars_daily_futures":
            return ["Code", "ProdCat"]
        elif self.symbol == "derivatives_bars_daily_options":
            return ["Code", "ProdCat", "UndSSO"]
        else:
            return ["Code"]
        

    @property
    def is_cvt(self):
        return True
    
class bld_sql(sqlbase):

    def __init__(self):
        return

    @property
    def is_cvt(self):
        # return False
        return True