

from scripts.download_util import *

def download_data(dump_skip_date_json: bool=False, fetch_time_length: int=20, fetch_time_scale: str='Y') -> None:
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
    DICC = DownloadIterationCheckCondition(dump_skip_date_json, fetch_time_length, fetch_time_scale)
    fetch_date_range = DICC.ABC.fetch_date_range
    for iter_n, date in enumerate(fetch_date_range, start=1):
        DICC.display_download_status(date, iter_n, len(fetch_date_range))
        DICC.resp_dict = DICC.ABC.fetch_all_resp(date)
        if DICC.iter_contents_check_ok(iter_n, date): 
            DICC.save_df_to_csv(date)
    DICC.dump_skip_date_dict_to_json()
    return