"""J-Quants APIからマーケットデータを取得するCLIスクリプト。

実行例:
    uv run download_data_main.py
    uv run download_data_main.py --range-type 1 --fetch-time-length 20 --fetch-time-scale Y
    uv run download_data_main.py --range-type 2 --from-date 2008-05-07 --to-date 2026-04-17
"""

from __future__ import annotations

import argparse

from scripts.download import download_data_async


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--range-type",
        dest="range_decision_type",
        choices=["1", "2"],
        default="2",
        help="1: fetch-time-length/-scale で相対期間指定, 2: from-date/to-date で絶対期間指定 (default: 2)",
    )
    parser.add_argument(
        "--fetch-time-length",
        type=int,
        default=2,
        help="range-type=1 の場合の取得期間の長さ (default: 2)",
    )
    parser.add_argument(
        "--fetch-time-scale",
        choices=["Y", "M", "D"],
        default="M",
        help="range-type=1 の場合の取得期間の単位 (default: M)",
    )
    parser.add_argument(
        "--from-date",
        dest="from_Date",
        default="2008-05-07",
        help="range-type=2 の場合の取得開始日 (default: 2008-05-07)",
    )
    parser.add_argument(
        "--to-date",
        dest="to_Date",
        default="2026-04-17",
        help="range-type=2 の場合の取得終了日 (default: 2026-04-17)",
    )
    parser.add_argument(
        "--async-semaphore-limit",
        type=int,
        default=5,
        help="非同期リクエストの同時実行数上限 (default: 5)",
    )
    parser.add_argument(
        "--per-sec-rate-limit",
        type=int,
        default=5,
        help="秒間リクエスト数上限 (default: 5)",
    )
    args = parser.parse_args()

    download_data_async(
        fetch_time_length=args.fetch_time_length,
        fetch_time_scale=args.fetch_time_scale,
        async_semaphore_limit=args.async_semaphore_limit,
        per_sec_rate_limit=args.per_sec_rate_limit,
        from_Date=args.from_Date,
        to_Date=args.to_Date,
        range_decision_type=args.range_decision_type,
    )


if __name__ == "__main__":
    main()
