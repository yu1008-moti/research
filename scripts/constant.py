from pathlib import Path


class paths:

    @property
    def CSVDATA_STORE_DIR(self):
        return Path("data_financial")
    
    @property
    def DB_STORE_DIR(self):
        return Path("db")

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
        return 'prc'

    @property
    def opt_tblnm(self):
        return 'drv_opt'

    @property
    def ftr_tblnm(self):
        return 'drv_ftr'
    
