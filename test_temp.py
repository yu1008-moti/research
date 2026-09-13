from scripts.datap.graph_v2.sql import fetch
from scripts.datap.graph_v2 import data_pipeline
from datetime import datetime as dt
from scripts.datap.graph_v2.sql import create

s = dt.now()
prices_df = fetch.prices()
financials_df = fetch.financials()

create.graph_info(serial_id=1)
pp = data_pipeline.preprocess(financials_df, prices_df, serial_id=1)
pp.insert_to_graph_info_table()
e = dt.now()
print(f"\nData insertion completed in {e - s}")