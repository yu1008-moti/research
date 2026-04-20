import pandas as pd
import requests
from typing import Dict, List, Any
from datetime import datetime as dt
from dateutil.relativedelta import relativedelta as rdt
from typing import Dict, List, Tuple
import os
import json
from math import log10


import asyncio
import aiohttp
import aiofiles


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

    def __init__(self, fetch_time_length: int = 20, fetch_time_scale: str='Y'):
        self.fetch_time_length = fetch_time_length
        self.fetch_time_scale = fetch_time_scale

    @property
    def diff(self) -> Tuple[int, str]:
        return (self.fetch_time_length, self.fetch_time_scale)

    @property
    def base_url(self) -> str:
        return "https://api.jquants.com/v2/"

    @property
    def fetch_date_range(self) -> List[str]:
        end_date = dt.today()
        if self.fetch_time_scale == 'Y':
            start_date = end_date - rdt(years=self.fetch_time_length)
        if self.fetch_time_scale == 'M':
            start_date = end_date - rdt(months=self.fetch_time_length)
        if self.fetch_time_scale == 'D':
            start_date = end_date - rdt(days=self.fetch_time_length)
        datetime_date_range = pd.date_range(start=start_date, end=end_date, freq="D")
        string_date_range = list(map(lambda x: x.strftime('%Y-%m-%d'), datetime_date_range))
        return string_date_range

    @property
    def endpts_base_list(self) -> List[str]:
        """
        0. 上場銘柄一覧 （equities/master）
        1. 価格データ   （equities/bars/daily）
        2. 財務情報     （fins/summary）
        """
        return list(map(lambda x: "/".join(x), [
            ["equities", "master"],
            ["equities", "bars", "daily"],
        ]))
    
    @property
    def endpts_additional_list(self) -> List[str]:
        """
        追加で取得したいデータのエンドポイントをここに記載する
        例えば、財務情報を取得したい場合は、以下のように記載する
        """
        return list(map(lambda x: "/".join(x), [
            ["equities", "investor-types"],
            ["markets", "margin-interest"],
            ["markets", "short-ratio"],
            ["fins", "summary"],
            ["fins", "details"],
            ["fins", "dividend"],
            ["indices", "bars", "daily"],
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
            'Date_1', 'Code_2', 
        ]
        return DROP_COLS


    def _fetch_one_resp(self, date: str, endpt: str, headers: Dict[str, str], base_url: str) -> List[Dict[str, Any]]:
        resp = requests.get(
            "%s/%s" % (base_url, endpt),
            params  = {"date": date},
            headers = headers,
        )
        resp = resp.json()['data']
        return resp


    def fetch_all_resp(self, date: str) -> Dict[str, Dict[str, List[Dict]]]:
        resp_dict = {'base': {}, 'additional': {}}
        for endpt in self.endpts_base_list:
            resp_dict['base'][endpt] = self._fetch_one_resp(date, endpt, self.headers, self.base_url)
        for endpt in self.endpts_additional_list:
            resp_dict['additional'][endpt] = self._fetch_one_resp(date, endpt, self.headers, self.base_url)
        return resp_dict


class DownloadIterationCheckCondition:


    def __init__(self, 
                 dump_skip_date_json: bool,
                fetch_time_length: int=20,
                fetch_time_scale: str='Y'
        ):
        
        self.df_one_before = pd.DataFrame()
        self.skip_date_dict = {}
        self.resp_dict = {}

        # self.save_encoding = "shift-jis"
        self.save_encoding = "utf-8"

        self.dump_skip_date_json = dump_skip_date_json
        self.ABC = ApiBasisConfig(fetch_time_length, fetch_time_scale)


    def _price_data_empty_condition(self) -> bool:
        prices_dict = self.resp_dict["base"][self.ABC.endpts_base_list[1]]
        return False if prices_dict == [] else True


    def _response_to_df(self, resp: List[Dict]) -> pd.DataFrame:
        df = pd.DataFrame.from_records(resp)
        return df


    def _response_length_mismatch_condition(self) -> bool:
        length_list = [len(df) for df in map(self._response_to_df, self.resp_dict["base"].values())]
        length_set = set(length_list)
        return False if len(length_set) != 1 else True


    def _update_skip_date_dict(self, iter_n: int, date: str) -> None:
        codes_df = self._response_to_df(self.resp_dict["base"][self.ABC.endpts_base_list[0]])
        next_buisness_date = codes_df['Date'].iloc[0]
        if next_buisness_date not in self.skip_date_dict:
            self.skip_date_dict[next_buisness_date] = []
        self.skip_date_dict[next_buisness_date].append((iter_n, date))
        return


    def _check_all_conditions(self) -> bool:
        if not self._price_data_empty_condition():
            return False
        if not self._response_length_mismatch_condition():
            return False
        self.df_one_before = self._response_to_df(self.resp_dict["base"][self.ABC.endpts_base_list[0]]).copy()
        return True
    

    def _save_base_df_to_csv(self, date: str) -> None:
        base_df = pd.concat(map(self._response_to_df, self.resp_dict["base"].values()), ignore_index=False, axis=1)
        base_df.to_csv("./csv/base/test_%s.csv" % date, index=False, encoding=self.save_encoding)
        return


    def _save_additional_df_to_csv(self, date: str) -> None:
        for endpt, resp in self.resp_dict["additional"].items():
            additional_df = self._response_to_df(resp)
            dir_path = "./csv/additional/%s" % endpt.replace("/", "_")
            os.makedirs(dir_path, exist_ok=True)
            additional_df.to_csv("%s/test_%s.csv" % (dir_path, date), index=False, encoding=self.save_encoding)
        return


############ DownloadIterationCheckConditionクラスのメソッドの実装を続ける ############


    def iter_contents_check_ok( 
            self,
            iter_n: int, 
            date: str, 
        ) -> bool:
        
        if self._check_all_conditions():
            result = True
        else:
            result = False
            self._update_skip_date_dict(iter_n, date)
        
        return result


    def dump_skip_date_dict_to_json(self) -> None:
        if self.dump_skip_date_json:
            with open("./json/skip_date_dict.json", "w") as f:
                json.dump(self.skip_date_dict, f, indent=4)
        return


    def save_df_to_csv(self, date: str) -> None:
        # df = df.drop(columns=ABC.drop_cols)
        self._save_base_df_to_csv(date)
        self._save_additional_df_to_csv(date)
        return


    def display_download_status(self, data_name, iter_num, max_iter_num):
        right_adjust_len = int(log10(max_iter_num)) + 1
        print(f"\r Downloading data for {data_name} (iteration {str(iter_num).rjust(right_adjust_len, ' ')}/{str(max_iter_num).rjust(right_adjust_len, ' ')})", end=" ")


    def download_data(self, dump_skip_date_json: bool=False, fetch_time_length: int=20, fetch_time_scale: str='Y') -> None:
        """
        1. 指定された期間の営業日ごとにAPIからデータを取得する．
        2. 取得したデータをCSVファイルとして保存する．

        Parameters
        ----------
        dump_skip_date_json : bool, optional
            データ取得を見送った日付をJSONファイルとして保存するかどうか， by default False
        fetch_time_length : int, optional
            取得するデータの期間の数， by default 20
        fetch_time_scale : str, optional
            取得するデータの期間の時間スケール， by default 'Y' 
            時間スケールは 'Y' (年), 'M' (月), 'D' (日) のいずれかを指定する．
        """
        fetch_date_range = self.ABC.fetch_date_range
        for iter_n, date in enumerate(fetch_date_range, start=1):
            self.display_download_status(date, iter_n, len(fetch_date_range))
            self.resp_dict = self.ABC.fetch_all_resp(date)
            if self.iter_contents_check_ok(iter_n, date):
                self.save_df_to_csv(date)
        self.dump_skip_date_dict_to_json()
        return

