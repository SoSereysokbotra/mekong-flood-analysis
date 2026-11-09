"""Level 7: the flood report, generated from the artefacts only.

The plan's deliverable is "a report a non-technical person could act on", with
the model's own limitation stated in the output. Every number in the report is
read from a results file here; nothing is typed by hand, so re-running the
upstream scripts re-writes the report.

Reads:  results/level4/{change_detection,normal_years,tierb_scores,
                        hidden_water_feasibility}.json
        results/level7/districts.json   (scripts/level7_district_areas.py)
        data/reference/tier_e_reference.json
Writes: results/level7/report.json      the headline numbers, one place
        docs/level7_report.md           the report
        docs/figures/level7_districts.png
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi.report import (  # noqa: F401
    BLUE,
    DISTRICTS,
    DOC,
    FIG,
    GRID,
    INK,
    L4,
    METHODS,
    MUTED,
    NAMES,
    OUT,
    SEL,
    build_report,
    build_report_data,
    day,
    generate_district_figure,
    km,
    load_json,
    render_report_markdown,
    rng,
)


def main():
    build_report()


if __name__ == "__main__":
    main()
