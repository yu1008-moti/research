from api.download import *

def main():
    print("Hello from research!")
    download_data(dump_skip_date_json=True, diff=(14, 'D'))


if __name__ == "__main__":
    main()