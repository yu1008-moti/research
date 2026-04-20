

from scripts.download_util_async import *


def download_data_async(fetch_time_length: int=20, fetch_time_scale: str='Y', async_semaphore_limit: int=50, per_sec_rate_limit: int=400) -> None:

    ApiL = ApiLauncher(
        fetch_time_length, 
        fetch_time_scale,
        async_semaphore_limit,
        per_sec_rate_limit
    )

    ApiL.start_download_async()

