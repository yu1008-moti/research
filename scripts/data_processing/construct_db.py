import sqlite3 as sql
import os

# equities_bars_daily.csv is exsits from 2009-05-07 to 2026-04-17
#   homogenous graph -> node = [daily-price-info], edge = [price-correlation]
# heterogenous graph -> node = [daily-price-info, quarterly-firm-info, yahoo-news, daily-index-info, other-quants-info], edge = [price-correlation]
def create_db(db_name):
    conn = sql.connect(db_name)
    c = conn.cursor()