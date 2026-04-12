import pandas as pd
import requests
from typing import Dict, List, Any
from datetime import datetime as dt
from dateutil.relativedelta import relativedelta as rdt
from typing import Dict, List, Tuple
import os
from math import log10


class ApiBasisConfig:
    """
    APIからデータを取得する際の基本的な設定をまとめたクラス
        - endpts_list: APIのエンドポイントのリスト
        - headers: APIリクエストのヘッダー情報（APIキーを含む）
        - drop_cols: 取得したデータから削除する列のリスト
        - その他、APIからデータを取得する際に必要な基本的な設定をここにまとめることができる
        - 例えば、APIのベースURLや、データ保存のパスなどもここに含めることができる
        - このクラスを使用することで、APIからデータを取得する際のコードがよりシンプルで読みやすくなる
    """

    @property
    def endpts_list(self) -> List[str]:
        """
        0. 上場銘柄一覧（equities/master）
        1. 価格データ（equities/bars/daily）
        """
        return list(map(lambda x: "/".join(x), [
            ["equities", "master"],
            ["equities", "bars", "daily"],
        ]))
    
    @property
    def headers(self) -> Dict[str, str]:
        env_value = os.getenv('jq_api_key')
        if env_value is None:
            raise ValueError("API key not found. Please set the 'jq_api_key' environment variable.")
        else:
            return {"x-api-key": env_value}
    
    @property
    def drop_cols(self) -> List[str]:
        DROP_COLS = [
            'O'     , 'H'     , 'L'    , 'C'     , 'Vo'     , 
            'AdjO'  , 'AdjH'  , 'AdjL' , 
            'MO'    , 'MH'    , 'ML'   , 'MC'    , 'MVo'    , 'MVa',
            'AAdjO' , 'AAdjH' , 'AAdjL', 'AAdjC' , 'AAdjVo' , 
            'AO'    , 'AH'    , 'AL'   , 'AC'    , 'AVo'    , 'AVa',
            'MAdjO' , 'MAdjH' , 'MAdjC', 'MAdjL' , 'MAdjVo' , 
            'UL'    , 'MUL'   , 'MLL'  , 'LL'    , 'AUL'    , 'ALL', 
        ]
        return DROP_COLS
    

def _fetch_one_resp(date, endpt, ABC) -> List[Dict[str, Any]]:
    resp = requests.get(
        "https://api.jquants.com/v2/%s" % endpt,
        params  = {"date": date},
        headers = ABC.headers,
    )
    resp = resp.json()['data']
    return resp


def _response_to_df(resp: List[Dict]) -> pd.DataFrame:
    df = pd.DataFrame.from_records(resp)
    return df


def save_df_to_csv(resp_dict: Dict[str, List[Dict]], date: str, ABC: ApiBasisConfig) -> None:
    df = pd.concat(map(_response_to_df, resp_dict.values()), ignore_index=True)
    # df = df.drop(columns=ABC.drop_cols)
    df.to_csv("./csv/test_%s.csv" % date, index=False, encoding="shift-jis")
    return


def iter_contents_check_ok(
        resp_dict: Dict[str, List[Dict]], 
        iter_n: int, 
        date: str, 
        df_one_before: pd.DataFrame, 
        skip_date_dict: Dict[str, List[Tuple[int, str]]],
        ABC: ApiBasisConfig
        ) -> bool:
    
    endpts_list = ABC.endpts_list
    codes_df  = _response_to_df(resp_dict[endpts_list[0]])
    
    # 1. 価格データが空の場合，その日付のデータ取得は見送る
    prices_dict = resp_dict[endpts_list[1]]
    if prices_dict == []:
        next_buisness_date = codes_df['Date'].iloc[0]
        if next_buisness_date not in skip_date_dict:
            skip_date_dict[next_buisness_date] = []
        skip_date_dict[next_buisness_date].append((iter_n, next_buisness_date))
        print(skip_date_dict)
        return False

    prices_df = _response_to_df(prices_dict)

    # 2. 各エンドポイントのレスポンスの長さが一致しない場合，そのデータ取得を見送る
    length_list = set([len(df) for df in [codes_df, prices_df]])
    if len(length_list) != 1:
        return False

    df_one_before = codes_df
    return True


def get_date_range(diff: Tuple[int, str], end_date: dt) -> List[str]:
    diff_timescale_map = {'Y': 'years', 'M': 'months', 'D': 'days'}
    if diff[1] == 'Y':
        start_date = end_date - rdt(years=diff[0])
    if diff[1] == 'M':
        start_date = end_date - rdt(months=diff[0])
    if diff[1] == 'D':
        start_date = end_date - rdt(days=diff[0])
    datetime_date_range = pd.date_range(start=start_date, end=end_date, freq="D")
    string_date_range = list(map(lambda x: x.strftime('%Y-%m-%d'), datetime_date_range))
    return string_date_range


def fetch_all_resp(date: str, ABC: ApiBasisConfig) -> Dict[str, List[Dict]]:
    endpts = ABC.endpts_list
    resp_dict = {}
    for endpt in endpts:
        resp_dict[endpt] = _fetch_one_resp(date, endpt, ABC)
    return resp_dict


def display_download_status(data_name, iter_num, max_iter_num):
    right_adjust_len = int(log10(max_iter_num)) + 1
    print(f"\r Downloading data for {data_name} (iteration {str(iter_num).rjust(right_adjust_len, ' ')}/{str(max_iter_num).rjust(right_adjust_len, ' ')})", end=" ")