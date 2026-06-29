from scripts.api.download_util_async import *

def download_data_async(
        fetch_time_length: int=20, 
        fetch_time_scale: str='Y', 
        async_semaphore_limit: int=50, 
        per_sec_rate_limit: int=400,
        from_Date: str="2008-05-07",
        to_Date: str="2026-04-17",
        range_decision_type: str="2"
        ) -> None:

    ApiL = ApiLauncher(
        fetch_time_length, 
        fetch_time_scale,
        async_semaphore_limit,
        per_sec_rate_limit,
        from_Date,
        to_Date,
        range_decision_type="2"
    )

    ApiL.start_download_async()


