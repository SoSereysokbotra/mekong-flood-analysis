"""Level 7, step 1: flood and flooded cropland per district, from the saved maps.

A province total tells nobody where to send help. This splits the Level 4
flood maps (peak 14 Oct 2020, and still flooded on 1 Nov) by district, for all
three methods, so the report can give each district a best estimate and a
range.

Districts: geoBoundaries KHM ADM2 (source Open Development Cambodia, 2014,
CC BY 4.0), the 9 districts of Banteay Meanchey, saved as
data/aoi/banteay_meanchey_adm2.geojson.

Outputs: results/level7/districts.{csv,json}
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi.report import (  # noqa: F401
    DISTRICTS,
    OUT,
    PEAK,
    POST,
    compute_district_areas,
    read_raster_mask,
    run_district_areas,
    write_district_areas,
)


def main():
    run_district_areas()


if __name__ == "__main__":
    main()
