"""Command-line interface for Mekong Flood Intelligence (mfi)."""
from __future__ import annotations

import argparse
import sys
from typing import Sequence

from mfi.check import CheckError, check_flood
from mfi.report import build_report, run_district_areas


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mfi",
        description="Mekong Flood Intelligence — Sentinel-1 radar flood detection for Cambodia.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available sub-commands")

    # mfi check
    p_check = subparsers.add_parser(
        "check",
        help="Check whether a Cambodian province is flooded on a given date vs historical baselines.",
    )
    p_check.add_argument("--date", help="YYYY-MM-DD; default: the latest radar pass")
    p_check.add_argument("--gap", type=int, default=18, help="days between 'before' and the date (default 18)")
    p_check.add_argument("--years", type=int, default=3, help="previous years to compare with (default 3; 0 = none)")
    p_check.add_argument("--province", help="default Banteay Meanchey; e.g. Battambang, 'Siem Reap'")
    p_check.add_argument("--track", help="force a track, e.g. 99, 99a (ascending) or 164d (descending)")

    # mfi report
    subparsers.add_parser(
        "report",
        help="Generate Level 7 flood intelligence report (docs/level7_report.md) from results artefacts.",
    )

    # mfi districts
    subparsers.add_parser(
        "districts",
        help="Compute Level 7 flood and flooded cropland per district from saved Level 4 maps.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "check":
            check_flood(
                date=args.date,
                gap=args.gap,
                years=args.years,
                province=args.province,
                track=args.track,
            )
        elif args.command == "report":
            build_report()
        elif args.command == "districts":
            run_district_areas()
    except CheckError as e:
        print(e, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
