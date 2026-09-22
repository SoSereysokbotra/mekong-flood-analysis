"""Route A backfill: add the cropland_bright / cropland_dark sub-strata to the
Level 1 results by re-scoring the *saved predictions* under results/level1/
<method>/pred/. Nothing is re-fitted or re-selected; the existing groups come
out identical and two groups are added. Each run/split gets a fresh log row
whose note says it is a backfill.
"""
import pathlib
import sys

import numpy as np
import rasterio
from tqdm import tqdm

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog, experiments, io, metrics, strata  # noqa: E402

LEVEL = "level1"
METHODS = ["otsu_vh_perchip", "otsu_vv_perchip", "otsu_vh_global", "otsu_vv_global", "authors_otsu"]


def main():
    split = catalog.s1f11_split()
    for method in METHODS:
        run_dir = experiments.run_dir(LEVEL, method)
        for s, chips in split.items():
            conf = metrics.Confusion()
            for chip in tqdm(chips, desc=f"{method:16s} {s}", leave=False):
                s1, label, grid = io.read_s1f11_chip(chip)
                land = strata.land_type(io.worldcover_chip(chip, grid))
                with rasterio.open(run_dir / "pred" / f"{chip}.tif") as src:
                    pred = src.read(1).astype(bool)
                conf.add(pred, label, land, vh=s1[1])
            m = experiments.save_split_results(LEVEL, method, s, conf, per_chip=[])
            experiments.log_row(LEVEL, method, s, method, {"backfill": "cropland_bright/dark from saved pred"},
                                len(chips), m, note="backfill of sub-strata from saved predictions; other groups unchanged")
            print(f"{method:16s} {s:5s}  cropland rec {m['cropland']['recall']:.3f} | "
                  f"bright rec {m['cropland_bright']['recall']:.3f} (n={m['cropland_bright']['n_pos']:,}) | "
                  f"dark rec {m['cropland_dark']['recall']:.3f} (n={m['cropland_dark']['n_pos']:,})")


if __name__ == "__main__":
    main()
