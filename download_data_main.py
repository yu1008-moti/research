from scripts.download import *

def main():
    print("Hello from research!")
    download_data_async(
        ### if you wanna use type[1], you change below
        ###     To get 20 years of past data from today,
        ###     Set fetch_time_length=20 and fetch_time_scale='Y'
        fetch_time_length=2, 
        fetch_time_scale='M', 
        async_semaphore_limit=5,
        per_sec_rate_limit=5,

        ### if you wanna use type[2], you change below
        from_Date="2008-05-07",
        to_Date="2026-04-17",

        ### type[1]: you decide fetch-time-length and fetch-time-scale
        ### type[2]: you decide from-date and to-date
        range_decision_type="2"
    )

if __name__ == "__main__":
    main()