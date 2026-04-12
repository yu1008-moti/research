import pandas as pd
from datetime import datetime as dt
from dateutil.relativedelta import relativedelta as rdt
from typing import Dict, List, Tuple

def test_response_to_df(resp):
    df = pd.DataFrame.from_records(resp)
    return df

def test_save_df_to_csv(df):
    df.to_csv("test.csv", index=False, encoding="shift-jis")
    return

def test_iter_download_info(df, iter_n, date, df_one_before, skip_date_dict):
    if df.equals(df_one_before):
        if date.strftime('%Y-%m-%d') not in skip_date_dict:
            skip_date_dict[date.strftime('%Y-%m-%d')] = []
        skip_date_dict[date.strftime('%Y-%m-%d')].append((iter_n, date.strftime('%Y-%m-%d')))
    else:
        test_save_df_to_csv(df)
        df_one_before = df
    return

def get_date_range(diff: int, end_date: dt) -> List[str]:
    start_date = end_date - rdt(years=diff)
    datetime_date_range = pd.date_range(start=start_date, end=end_date, freq="D")
    string_date_range = list(map(lambda x: x.strftime('%Y-%m-%d'), datetime_date_range))
    return string_date_range