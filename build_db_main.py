from scripts.build_db import *
from scripts.constant import doc_symbols, tbl_names, msg
import sys

def main():
    print("Hello from research!")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        db_type = sys.argv[1]
        DC, TN = doc_symbols(), tbl_names()
        m = msg()

        # Handle price database
        if db_type == "price":
            symbols, table_name = [DC.prc_mstr, DC.prc_bars], TN.prc_tblnm

            # Build the price database
            build_prc_db(symbols, table_name)
        
        # Handle derivatives database
        elif db_type == "drv":

            # Initialize drv_flag to None
            drv_flag = None

            # validate that the flag is provided
            if len(sys.argv) < 3:
                print(m.missing_drv_flag)
                sys.exit(1)
            
            # Get the flag from command line arguments
            drv_flag = sys.argv[2] if len(sys.argv) > 2 else None

            # Determine the symbol and table name based on the flag
            if drv_flag == "-f":
                symbol, table_name = DC.ftr, TN.ftr_tblnm
            elif drv_flag == "-o":
                symbol, table_name = DC.opt, TN.opt_tblnm
            
            # Handle invalid flag and exit the program
            else:
                print(m.invalid_drv_flag)
                sys.exit(1)
            
            # Build the derivatives database
            build_drv_db(symbol, table_name)
        
        # Handle invalid database type
        else:
            print(m.invalid_db_type)

    print(m.completed)