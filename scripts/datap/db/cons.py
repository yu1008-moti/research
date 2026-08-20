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
    

    @property
    def missing_fin_flag(self):
        return "Missing flag for financial database. Please use '--detail', '--dividend', or '--summary'."
    
    @property
    def invalid_fin_flag(self):
        return "Invalid flag for financial database. Please use '--detail', '--dividend', or '--summary'."
    
    @property
    def missing_mkt_flag(self):
        return "Missing flag for markets database. Please use '--breakdown', '--margin-alert', '--margin-interest', or '--short-ratio'."
    
    @property
    def invalid_mkt_flag(self):
        return "Invalid flag for markets database. Please use '--breakdown', '--margin-alert', '--margin-interest', or '--short-ratio'."
    
    # Messages related to database conversion

    @property
    def convert_db_start(self):
        return "Start converting database from SQLite to DuckDB..."
    
    @property
    def convert_db_end(self):
        return "Database conversion completed successfully."
    

class doc_symbols:

    ### equities database series

    @property
    def prc_bars(self):
        return 'equities_bars_daily'
    
    @property
    def prc_mstr(self):
        return 'equities_master'
    
    @property
    def inv(self):
        return 'equities_investor-types'
    
    ### derivatives database series

    @property
    def opt(self):
        return 'derivatives_bars_daily_options'

    @property
    def ftr(self):
        return 'derivatives_bars_daily_futures'
    
    ### indices database series
    
    @property
    def idx(self):
        return 'indices_bars_daily'

    ### markets database series
    
    @property
    def bkd(self):
        return 'markets_breakdown'
    
    @property
    def mga(self):
        return 'markets_margin-alert'
    
    @property
    def mgi(self):
        return 'markets_margin-interest'
    
    @property
    def shr(self):
        return 'markets_short-ratio'

    ### financial database series
    
    @property
    def det(self):
        return 'fins_details'
    
    @property
    def div(self):
        return 'fins_dividend'

    @property
    def sum(self):
        return 'fins_summary'
    


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
    
    @property
    def inv_tblnm(self):
        return 'eqt_inv'
    
    @property
    def idx_tblnm(self):
        return 'idx_prc'
    
    @property
    def bkd_tblnm(self):
        return 'bkd_qtt'
    
    @property
    def mga_tblnm(self):
        return 'mga_qtt'

    @property
    def mgi_tblnm(self):
        return 'mgi_qtt'
    
    @property
    def shr_tblnm(self):
        return 'shr_qtt'
    
    @property
    def det_tblnm(self):
        return 'fin_det'
    
    @property
    def div_tblnm(self):
        return 'fin_div'
    
    @property
    def sum_tblnm(self):
        return 'fin_sum'
    


class nums:

    @property
    def DUCKDB_CVT_CFG(self):
        chunk_size = 500_000
        offset = 0
        return (chunk_size, offset)


### related SQL classes for building and converting databases
class sqlbase:

    def __init__(self, symbol: str):
        self.symbol = symbol

    @property
    def Datelike_cols(self):
        if self.symbol == "equities_bars_daily":
            return ["Date"]
        elif self.symbol == "derivatives_bars_daily_futures":
            return ["Date", "LTD", "SQD"]
        elif self.symbol == "derivatives_bars_daily_options":
            return ["Date", "LTD", "SQD"]
        elif self.symbol == "equities_investor-types":
            return ["PubDate", "StDate", "EnDate"]
        elif self.symbol == "indices_bars_daily":
            return ["Date"]
        elif self.symbol == "markets_breakdown":
            return ["Date"]
        elif self.symbol == "fins_summary":
            return ["DiscDate", "CurPerSt", "CurPerEn", "CurFYSt", "CurFYEn"]
        elif self.symbol == "fins_details":
            return ["DiscDate"]
        elif self.symbol == "fins_dividend":
            return ["PubDate", "BoardDate", "RecDate", "ExDate", "PayDate"]
        elif self.symbol == "markets_margin-alert":
            return ["PubDate", "AppDate"]
        elif self.symbol == "markets_margin-interest":
            return ["Date"]
        elif self.symbol == "markets_short-ratio":
            return ["Date"]
        else:
            return ["Date"]
    
    @property
    def Text_cols(self):
        if self.symbol == "equities_bars_daily":
            return ["Code", "CoName", "CoNameEn", "S17Nm", "S33Nm", "ScaleCat", "MktNm", "MrgnNm"]
        elif self.symbol == "derivatives_bars_daily_futures":
            return ["Code", "CM", "ProdCat"]
        elif self.symbol == "derivatives_bars_daily_options":
            return ["Code", "CM", "ProdCat", "UndSSO"]
        elif self.symbol == "equities_investor-types":
            return ["Section"]
        elif self.symbol == "indices_bars_daily":
            return ["Code"]
        elif self.symbol == "markets_breakdown":
            return ["Code"]
        elif self.symbol == "fins_summary":
            return ["DiscTime", "Code", "DocType", "CurPerType"]
        elif self.symbol == "fins_details":
            return ["DiscTime", "Code", "DocType", "FS"]
        elif self.symbol == "fins_dividend":
            return ["PubTime", "Code", "IFTerm"]
        elif self.symbol == "markets_margin-alert":
            return ["Code", "PubReason"]
        elif self.symbol == "markets_margin-interest":
            return ["Code"]
        elif self.symbol == "markets_short-ratio":
            return []
        else:
            return ["Code"]

    @property
    def ALL_IS_SAME(self): ...
    
    @property
    def is_cvt(self): ...
    

class cvt_sql(sqlbase):

    def __init__(self, symbol:str):
        super().__init__(symbol)        

    @property
    def is_cvt(self):
        return True
    

class bld_sql(sqlbase):

    def __init__(self, symbol:str):
        super().__init__(symbol)

        
    @property
    def ALL_IS_SAME(self):
        if self.symbol == "equities_investor-types":
            return True
        else:
            return False

    @property
    def is_cvt(self):
        return False
        # return True # RECOMENDATION: Set to False to prevent conversion during database building.


