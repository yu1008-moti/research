import requests
import pandas as pd
from datetime import datetime as dt
import os 

from test_api_util import *

headers = {"x-api-key": os.getenv('jq_api_key')}

def test_get_response(date):
    resp = requests.get(
        "https://api.jquants.com/v2/equities/master",
        params  = {"date": date},
        headers = headers,
    )
    resp = resp.json()['data']
    return resp


def test_download_info(end_date):
    df_one_before = pd.DataFrame()
    skip_date_dict = {}
    for iter_n, date in enumerate(get_date_range(20, end_date), start=1):
        print(f"\r Downloading data for {date} (iteration {iter_n})", end="  ")
        df = test_response_to_df(test_get_response(date))
        test_iter_download_info(df, iter_n, date, df_one_before, skip_date_dict)
    return

if __name__ == "__main__":
    test_download_info(dt.today())