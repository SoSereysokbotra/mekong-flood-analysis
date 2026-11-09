"""Is a Cambodian province flooded on a given date? One command, any date with radar.

    python scripts/check_flood.py --date 2026-09-26                 # Banteay Meanchey
    python scripts/check_flood.py --province Battambang             # newest radar pass
    python scripts/check_flood.py --province Battambang --track 99  # force a track

What it does, in the same way as Level 4:
  1. finds the Sentinel-1 pass on (or just before) --date, and the pass --gap
     days earlier as "before" (default 18, as in the 2020 study). Banteay
     Meanchey uses track 164 descending, the study track. Any other province
     uses the track that covers most of it in the 30 days before the date;
  2. runs the three methods on both, 20 m over the whole province;
     flood = water on the date that was not water before;
  3. compares with the same dates in the --years previous years, because in
     the wet season a lot of new water is ordinary paddy ponding, not a flood;
  4. writes a map, a per-district table and a short plain-language report.

The verdict is a stated rule, not a measured accuracy:
    UNUSUAL FLOODING   flooded cropland (selected model) is more than
                       VERDICT_RATIO x the median of the previous years
                       and more than VERDICT_MIN_KM2
    NORMAL FOR THE SEASON otherwise
The rule was not tuned on any event. The 2020 event is 6.0x its baseline.

Downloads ~350 MB per radar pass (2 per year compared): run it on Colab
(notebooks/colab_check_flood.ipynb), not on a slow home connection.

Province borders: geoBoundaries KHM ADM1/ADM2 (Open Development Cambodia,
2014, CC BY 4.0) in data/aoi/. Banteay Meanchey keeps its original files and
caches, so its numbers do not change.

Outputs: results/check/<date>/ for Banteay Meanchey,
         results/check/<province>/<date>/ for any other province:
         report.md, summary.json, districts.csv, map.png, flood_<method>.tif
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi.check import (  # noqa: F401
    ADM1,
    ADM2,
    MIN_COVERAGE,
    NAMES,
    OUT,
    SEL,
    VERDICT_MIN_KM2,
    VERDICT_RATIO,
    CheckError,
    Predictor,
    Region,
    check_flood,
    compute_districts,
    compute_flood,
    compute_verdicts,
    flood_pair,
    key,
    parse_date,
    pass_nearest,
    pass_on_or_before,
    passes,
    s1_retry,
    write_outputs,
)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--date", help="YYYY-MM-DD; default: the latest radar pass")
    ap.add_argument("--gap", type=int, default=18, help="days between 'before' and the date (default 18)")
    ap.add_argument("--years", type=int, default=3, help="previous years to compare with (default 3; 0 = none)")
    ap.add_argument("--province", help="default Banteay Meanchey; e.g. Battambang, 'Siem Reap'")
    ap.add_argument("--track", help="force a track, e.g. 99, 99a (ascending) or 164d (descending)")
    a = ap.parse_args()

    try:
        check_flood(date=a.date, gap=a.gap, years=a.years, province=a.province, track=a.track)
    except CheckError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
