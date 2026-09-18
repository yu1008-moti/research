from scripts.build_db import *
from scripts.datap.db.constant import doc_symbols, tbl_names, msg
import sys

def main():
    print("Hello from research!")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        op_type = sys.argv[1]
        db_type = sys.argv[2] if len(sys.argv) > 2 else None
        DC, TN = doc_symbols(), tbl_names()
        m = msg()

        # BUILD SCRATCH database operation
        #   1. build sqlite database from csv files
        #   2. convert sqlite database to duckdb database
        if op_type == "-b":


            # Handle price database
            if db_type == "prc":
                symbols, table_name = [DC.prc_mstr, DC.prc_bars], TN.prc_tblnm

                # Build the price database
                build_prc_db(symbols, table_name)
            
            # Handle derivatives database
            #   -f for futures
            #   -o for options
            elif db_type == "drv":

                # Initialize drv_flag to None
                drv_flag = None

                # validate that the flag is provided
                if len(sys.argv) < 4:
                    print(m.missing_drv_flag)
                    sys.exit(1)
                
                # Get the flag from command line arguments
                drv_flag = sys.argv[3] if len(sys.argv) > 3 else None

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
        

            # Handle inventory database
            # NO flag is needed for inventory database
            elif db_type == "inv":
                symbol, table_name = DC.inv, TN.inv_tblnm

                # Build the inventory database
                build_inv_db(symbol, table_name)
        

            # Handle indices database
            # NO flag is needed for indices database
            elif db_type == "idx":
                symbol, table_name = DC.idx, TN.idx_tblnm

                # Build the indices database
                build_idx_db(symbol, table_name)


            # Handle futures settlement database
            #   --detail for details
            #   --dividend for dividends
            #   --summary for summary
            elif db_type == "fin":

                # Initialize fin_flag to None
                fin_flag = None

                # validate that the flag is provided
                if len(sys.argv) < 4:
                    print(m.missing_fin_flag)
                    sys.exit(1)
                
                # Get the flag from command line arguments
                fin_flag = sys.argv[3] if len(sys.argv) > 3 else None

                # Determine the symbol and table name based on the flag
                if fin_flag == "--detail":
                    symbol, table_name = DC.det, TN.det_tblnm
                elif fin_flag == "--dividend":
                    symbol, table_name = DC.div, TN.div_tblnm
                elif fin_flag == "--summary":
                    symbol, table_name = DC.sum, TN.sum_tblnm
                
                # Handle invalid flag and exit the program
                else:
                    print(m.invalid_fin_flag)
                    sys.exit(1)

                # Build the futures settlement database
                build_fin_db(symbol, table_name)
        

            # Handle markets database
            #   --breakdown for breakdown
            #   --margin-alert for margin alert
            #   --margin-interest for margin interest
            #   --short-ratio for short ratio
            elif db_type == "mkt":

                # Initialize mkt_flag to None
                mkt_flag = None

                # validate that the flag is provided
                if len(sys.argv) < 4:
                    print(m.missing_mkt_flag)
                    sys.exit(1)
                
                # Get the flag from command line arguments
                mkt_flag = sys.argv[3] if len(sys.argv) > 3 else None

                # Determine the symbol and table name based on the flag
                if mkt_flag == "--breakdown":
                    symbol, table_name = DC.bkd, TN.bkd_tblnm
                elif mkt_flag == "--margin-alert":
                    symbol, table_name = DC.mga, TN.mga_tblnm
                elif mkt_flag == "--margin-interest":
                    symbol, table_name = DC.mgi, TN.mgi_tblnm
                elif mkt_flag == "--short-ratio":
                    symbol, table_name = DC.shr, TN.shr_tblnm
                
                # Handle invalid flag and exit the program
                else:
                    print(m.invalid_mkt_flag)
                    sys.exit(1)
                
                # Build the derivatives database
                build_drv_db(symbol, table_name)
        


        # CONVERT ONLY database operation
        #   1. convert sqlite database to duckdb database
        elif op_type == "-c":

            # Handle price database conversion
            if db_type == "prc":
                symbol, table_name = DC.prc_bars, TN.prc_tblnm
                sqlite2duckdb(symbol, table_name)


            # Handle derivatives database conversion
            #   -f for futures
            #   -o for options
            elif db_type == "drv":

                drv_flag = None

                # validate that the flag is provided
                if len(sys.argv) < 4:
                    print(m.missing_drv_flag)
                    sys.exit(1)
                
                # Get the flag from command line arguments
                drv_flag = sys.argv[3] if len(sys.argv) > 3 else None

                # Determine the symbol and table name based on the flag
                if drv_flag == "-f":
                    symbol, table_name = DC.ftr, TN.ftr_tblnm
                elif drv_flag == "-o":
                    symbol, table_name = DC.opt, TN.opt_tblnm
                
                # Handle invalid flag and exit the program
                else:
                    print(m.invalid_drv_flag)
                    sys.exit(1)

                sqlite2duckdb(symbol, table_name)
        

            # Handle inventory database conversion
            # NO flag is needed for inventory database
            elif db_type == "inv":
                symbol, table_name = DC.inv, TN.inv_tblnm
                sqlite2duckdb(symbol, table_name)
            

            # Handle indices database conversion
            # NO flag is needed for indices database
            elif db_type == "idx":
                symbol, table_name = DC.idx, TN.idx_tblnm
                sqlite2duckdb(symbol, table_name)


            # Handle markets database conversion
            #   --breakdown for breakdown
            #   --margin-alert for margin alert
            #   --margin-interest for margin interest
            #   --short-ratio for short ratio
            elif db_type == "mkt":

                mkt_flag = None

                # validate that the flag is provided
                if len(sys.argv) < 4:
                    print(m.missing_mkt_flag)
                    sys.exit(1)

                # Get the flag from command line arguments
                mkt_flag = sys.argv[3] if len(sys.argv) > 3 else None

                # Determine the symbol and table name based on the flag
                if mkt_flag == "--breakdown":
                    symbol, table_name = DC.bkd, TN.bkd_tblnm
                elif mkt_flag == "--margin-alert":
                    symbol, table_name = DC.mga, TN.mga_tblnm
                elif mkt_flag == "--margin-interest":
                    symbol, table_name = DC.mgi, TN.mgi_tblnm
                elif mkt_flag == "--short-ratio":
                    symbol, table_name = DC.shr, TN.shr_tblnm

                # Handle invalid flag and exit the program
                else:
                    print(m.invalid_mkt_flag)
                    sys.exit(1)

                sqlite2duckdb(symbol, table_name)


            # Handle futures settlement database conversion
            #   --detail for details
            #   --dividend for dividends
            #   --summary for summary
            elif db_type == "fin":
                fin_flag = None

                # validate that the flag is provided
                if len(sys.argv) < 4:
                    print(m.missing_fin_flag)
                    sys.exit(1)
                
                # Get the flag from command line arguments
                fin_flag = sys.argv[3] if len(sys.argv) > 3 else None

                # Determine the symbol and table name based on the flag
                if fin_flag == "--detail":
                    symbol, table_name = DC.det, TN.det_tblnm
                elif fin_flag == "--dividend":
                    symbol, table_name = DC.div, TN.div_tblnm
                elif fin_flag == "--summary":
                    symbol, table_name = DC.sum, TN.sum_tblnm

                # Handle invalid flag and exit the program
                else:
                    print(m.invalid_fin_flag)
                    sys.exit(1)

                sqlite2duckdb(symbol, table_name)
        # Handle invalid database type
        else:
            print(m.invalid_db_type)

    print(m.completed)