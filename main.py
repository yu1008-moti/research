from api.download import *

def main():
    print("Hello from research!")
    download_data(dump_skip_date_json=True, fetch_time_length=14, fetch_time_scale='D')


if __name__ == "__main__":
    main()