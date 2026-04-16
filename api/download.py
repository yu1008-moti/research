

from scripts.download_util import *
def download_data(dump_skip_date_json: bool=False, fetch_time_length: int=20, fetch_time_scale: str='Y') -> None:
    DICC = DownloadIterationCheckCondition(
        dump_skip_date_json, 
        fetch_time_length, 
        fetch_time_scale
    )
    DICC.download_data()