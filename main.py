from scripts.data.download import *

def main():
    print("Hello from research!")
    download_data_async(
        fetch_time_length=20, 
        fetch_time_scale='Y', 
        async_semaphore_limit=5,
        per_sec_rate_limit=5
    )

if __name__ == "__main__":
    main()