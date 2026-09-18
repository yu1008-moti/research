"""CSV/APIデータからSQLiteデータベースを構築し、DuckDBへ変換するCLIスクリプト。

実行例:
    uv run build_db_main.py build prc
    uv run build_db_main.py build drv -f
    uv run build_db_main.py convert drv -o
    uv run build_db_main.py build fin --detail
    uv run build_db_main.py build mkt --breakdown
"""

from __future__ import annotations

import argparse
import sys

from scripts.build_db import *
from scripts.datap.db.cons import doc_symbols, tbl_names, msg

DB_TYPES = ["prc", "drv", "inv", "idx", "fin", "mkt"]


def _add_flagged_options(parser: argparse.ArgumentParser) -> None:
    drv_group = parser.add_mutually_exclusive_group()
    drv_group.add_argument(
        "-f", dest="drv_flag", action="store_const", const="-f", help="db-type=drv: 先物 (futures)"
    )
    drv_group.add_argument(
        "-o", dest="drv_flag", action="store_const", const="-o", help="db-type=drv: オプション (options)"
    )

    fin_group = parser.add_mutually_exclusive_group()
    fin_group.add_argument(
        "--detail", dest="fin_flag", action="store_const", const="--detail", help="db-type=fin: 決算詳細"
    )
    fin_group.add_argument(
        "--dividend", dest="fin_flag", action="store_const", const="--dividend", help="db-type=fin: 配当情報"
    )
    fin_group.add_argument(
        "--summary", dest="fin_flag", action="store_const", const="--summary", help="db-type=fin: 決算サマリー"
    )

    mkt_group = parser.add_mutually_exclusive_group()
    mkt_group.add_argument(
        "--breakdown",
        dest="mkt_flag",
        action="store_const",
        const="--breakdown",
        help="db-type=mkt: 売買内訳",
    )
    mkt_group.add_argument(
        "--margin-alert",
        dest="mkt_flag",
        action="store_const",
        const="--margin-alert",
        help="db-type=mkt: 信用取引残高（注意喚起銘柄）",
    )
    mkt_group.add_argument(
        "--margin-interest",
        dest="mkt_flag",
        action="store_const",
        const="--margin-interest",
        help="db-type=mkt: 信用取引残高（金利）",
    )
    mkt_group.add_argument(
        "--short-ratio",
        dest="mkt_flag",
        action="store_const",
        const="--short-ratio",
        help="db-type=mkt: 空売り比率",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="op", required=True)

    build_p = subparsers.add_parser("build", help="CSV/APIデータからSQLiteデータベースを構築する")
    build_p.add_argument("db_type", choices=DB_TYPES)
    _add_flagged_options(build_p)

    convert_p = subparsers.add_parser("convert", help="SQLiteデータベースをDuckDBへ変換する")
    convert_p.add_argument("db_type", choices=DB_TYPES)
    _add_flagged_options(convert_p)

    return parser


def _resolve_symbol_and_table(args: argparse.Namespace, DC, TN, m):
    db_type = args.db_type

    if db_type == "prc":
        if args.op == "build":
            return [DC.prc_mstr, DC.prc_bars], TN.prc_tblnm
        return DC.prc_bars, TN.prc_tblnm

    if db_type == "drv":
        if args.drv_flag is None:
            print(m.missing_drv_flag)
            sys.exit(1)
        return (DC.ftr, TN.ftr_tblnm) if args.drv_flag == "-f" else (DC.opt, TN.opt_tblnm)

    if db_type == "inv":
        return DC.inv, TN.inv_tblnm

    if db_type == "idx":
        return DC.idx, TN.idx_tblnm

    if db_type == "fin":
        if args.fin_flag is None:
            print(m.missing_fin_flag)
            sys.exit(1)
        return {
            "--detail": (DC.det, TN.det_tblnm),
            "--dividend": (DC.div, TN.div_tblnm),
            "--summary": (DC.sum, TN.sum_tblnm),
        }[args.fin_flag]

    # db_type == "mkt"
    if args.mkt_flag is None:
        print(m.missing_mkt_flag)
        sys.exit(1)
    return {
        "--breakdown": (DC.bkd, TN.bkd_tblnm),
        "--margin-alert": (DC.mga, TN.mga_tblnm),
        "--margin-interest": (DC.mgi, TN.mgi_tblnm),
        "--short-ratio": (DC.shr, TN.shr_tblnm),
    }[args.mkt_flag]


def main() -> None:
    args = build_parser().parse_args()
    DC, TN, m = doc_symbols(), tbl_names(), msg()
    symbol, table_name = _resolve_symbol_and_table(args, DC, TN, m)

    if args.op == "build":
        if isinstance(symbol, list):
            if args.db_type == "prc":
                build_prc_db(symbol, table_name)
        else:
            if args.db_type == "drv":
                build_drv_db(symbol, table_name)
            elif args.db_type == "inv":
                build_inv_db(symbol, table_name)
            elif args.db_type == "idx":
                build_idx_db(symbol, table_name)
            elif args.db_type == "fin":
                build_fin_db(symbol, table_name)
            elif args.db_type == "mkt":
                build_mbd_db(symbol, table_name)
    else:  # args.op == "convert"
        assert isinstance(symbol, str), "symbol must be a string for conversion"
        sqlite2duckdb(symbol, table_name)

    print(m.completed)


if __name__ == "__main__":
    main()
