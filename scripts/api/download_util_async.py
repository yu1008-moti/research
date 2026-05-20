import logging
from urllib import response

from matplotlib import dates
import pandas as pd
import requests
from typing import Dict, List, Any
from datetime import datetime as dt
import time
from dateutil.relativedelta import relativedelta as rdt
from typing import Dict, List, Tuple
import os
import json
from math import log10
import itertools

import asyncio
import aiohttp

import sqlite3 as sql

from logging import getLogger


class ApiLauncher:
    """
    APIからデータを取得する際の基本的な設定をまとめたクラス
        - endpts_list: APIのエンドポイントのリスト
        - headers: APIリクエストのヘッダー情報（APIキーを含む）
        - drop_cols: 取得したデータから削除する列のリスト
        - その他、APIからデータを取得する際に必要な基本的な設定をここにまとめることができる
        - 例えば、APIのベースURLや、データ保存のパスなどもここに含めることができる
        - このクラスを使用することで、APIからデータを取得する際のコードがよりシンプルで読みやすくなる
    """

    def __init__(self, fetch_time_length: int = 20, fetch_time_scale: str='Y', async_semaphore_limit: int = 10, per_sec_rate_limit: int = 400) -> None:
        self.fetch_time_length = fetch_time_length
        self.fetch_time_scale = fetch_time_scale
        self.async_semaphore_limit = async_semaphore_limit
        self.rate_limit = per_sec_rate_limit

        self.api_queue = asyncio.Queue(maxsize=1000)
        self.save_encoding = "utf-8"
        self.last_called = 0
        self.interval = 1 / self.rate_limit  # 500 req/s but some margin for error, so 400 req/s

        logging.basicConfig(
            filename=f"logs/{dt.now().strftime('%Y-%m-%d_%H-%M-%S')}.log", 
            level=logging.ERROR, 
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        self.logger = getLogger(__name__)
        

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
    def endpts_list(self) -> List[str]:
        """
        追加で取得したいデータのエンドポイントをここに記載する
        例えば、財務情報を取得したい場合は、以下のように記載する
        """
        return list(map(lambda x: "/".join(x), [
            ["equities", "master"],                             # 上場銘柄一覧
            ["equities", "bars", "daily"],                      # 株価四本値データ（日足）
        ]))  + list(map(lambda x: "/".join(x), [
            ["equities", "investor-types"],                     # 投資部門別情報
            ["markets", "margin-interest"],                     # 信用取引週末残高
            ["markets", "short-ratio"],                         # 業種別空売り比率
            ["markets", "short-sale-report"],                   # 空売り残高報告
            ["markets", "margin-alert"],                        # 日々公表信用取引残高
            ["markets", "breakdown"],                           # 売買内訳データ
            ["markets", "calendar"],                            # 取引カレンダー
            ["indices", "bars", "daily"],                       # 指数四本値
            ["indices", "bars", "daily", "topix"],              # TOPIXオプション四本値 
            ["fins", "summary"],                                # 財務情報
            ["fins", "details"],                                # 財務諸表（BS/PL/CF）
            ["fins", "dividend"],                               # 配当金情報
            ["equities", "earnings-calendar"],                  # 決算発表予定日
            ["derivatives", "bars", "daily", "options", "225"], # 日経225オプション四本値
            ["derivatives", "bars", "daily", "futures"],        # 先物四本値
            ["derivatives", "bars", "daily", "options"]         # オプション四本値
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
    
    @property
    def max_fetch_num(self) -> int:
        return len(self.fetch_date_range) * len(self.endpts_list)

    def _get_file_path(self, date: str, endpt: str) -> str:
        dir_path = f"./csv/{date}"
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
        file_path = f"{dir_path}/{endpt.replace('/', '_')}.csv"
        return file_path

    async def _rate_limited(self):
        now = time.time()
        wait = self.interval - (now - self.last_called)
        if wait > 0:
            await asyncio.sleep(wait)
        self.last_called = time.time()

    # コルーチンが実行されるのはgatherの中で、fetch_respが完了するまで待機する
    async def _fetch_resp(self, semaphore: asyncio.Semaphore, session: aiohttp.ClientSession, date: str, endpt: str) -> Tuple[str, str, Dict]:
        url = "%s/%s" % (self.base_url, endpt)
        params = {"date": date}
        async with semaphore:
            await self._rate_limited()
            async with session.get(url=url, headers=self.headers, params=params) as response:
                resp_data = await response.json()
                return date, endpt, resp_data

    async def _api_Producer(self) -> None:
        semaphore = asyncio.Semaphore(self.async_semaphore_limit)  # Limit the number of concurrent requests
        tasks = []
        async with aiohttp.ClientSession() as session:
            for date, endpt in itertools.product(self.fetch_date_range, self.endpts_list):
                tasks.append(self._fetch_resp(semaphore, session, date, endpt))

            for coroutine in asyncio.as_completed(tasks):
                date, endpt, resp_data = await coroutine
                # ここでresp_dataを処理する（例: APIキューに追加）
                await self.api_queue.put((date, endpt, resp_data))
        
        await self.api_queue.put((None, None, None))  # Sentinel value to indicate completion

    async def _api_Consumer(self) -> None:
        cnt = 0
        max_cnt = self.max_fetch_num
        file_path_justified_length = max([len(self._get_file_path(date, endpt)) for date, endpt in itertools.product(self.fetch_date_range, self.endpts_list)])
        log10_max_cnt = int(log10(max_cnt)) + 1
        while True:
            date, endpt, resp_data = await self.api_queue.get()
            file_path = self._get_file_path(date, endpt)

            # ここでitemを処理する（例: CSVに保存）
            if date is None:  # Sentinel valueを受け取ったら終了
                break
            if 'data' not in resp_data:
                self.logger.error(f"No data for {self._get_file_path(date, endpt)}")
                print(
                f"\rNG {file_path.ljust(file_path_justified_length)} | time: {dt.now() - self.start_time} | progress: {str(cnt+1).rjust(log10_max_cnt)}/{str(max_cnt)} ({(cnt+1)/max_cnt*100:.2f}%)",
                end=" "
                )
                cnt += 1
                self.api_queue.task_done()
                continue
            df = pd.DataFrame.from_records(resp_data['data'])
            df.to_csv(file_path, index=False, encoding=self.save_encoding)
            # console display
            print(
                f"\rOK {file_path.ljust(file_path_justified_length)} | time: {dt.now() - self.start_time} | progress: {str(cnt+1).rjust(log10_max_cnt)}/{str(max_cnt)} ({(cnt+1)/max_cnt*100:.2f}%)",
                end=" "
            )
            cnt += 1
            self.api_queue.task_done()

    async def _main(self) -> None:
        self.start_time = dt.now()
        producer_task = asyncio.create_task(self._api_Producer())
        consumer_task = asyncio.create_task(self._api_Consumer())
        await asyncio.gather(producer_task, consumer_task)

    def start_download_async(self) -> None:
        asyncio.run(self._main())
        # self.dump_skip_date_dict_to_json()
        return
    
