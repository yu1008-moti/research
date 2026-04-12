import requests
import pandas as pd
from datetime import datetime as dt
import json
from typing import List, Dict, Tuple

from scripts.download_util import *


def download_data(dump_skip_date_json: bool=False, diff: Tuple[int, str]=(20, 'Y')) -> None:
    """
    1. 指定された期間の営業日ごとにAPIからデータを取得する．
    2. 取得したデータをCSVファイルとして保存する．

    Parameters
    ----------
    dump_skip_date_json : bool, optional
        データ取得を見送った日付をJSONファイルとして保存するかどうか， by default False
    diff : Tuple[int, str], optional
        取得するデータの期間を指定するタプル (期間の数, 時間スケール)， by default (20, 'Y')
        時間スケールは 'Y' (年), 'M' (月), 'D' (日) のいずれかを指定する．
    """
    ABC = ApiBasisConfig()
    df_one_before, skip_date_dict = pd.DataFrame(), {}
    date_range = get_date_range(diff, dt.today())
    for iter_n, date in enumerate(date_range, start=1):
        display_download_status(date, iter_n, len(date_range))
        resp_dict = fetch_all_resp(date, ABC)
        if iter_contents_check_ok(
            resp_dict, 
            iter_n, 
            date, 
            df_one_before, 
            skip_date_dict,
            ABC
        ): 
            save_df_to_csv(resp_dict, date, ABC)
    if dump_skip_date_json:
        with open("./json/skip_date_dict.json", "w") as f:
            json.dump(skip_date_dict, f, indent=4)
    return