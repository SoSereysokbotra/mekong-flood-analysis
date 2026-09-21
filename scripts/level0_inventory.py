"""Level 0 inventory: how many flooded-cropland pixels does Sen1Floods11 have?

For every hand-labelled chip:
  1. read S1 (dB) + hand label, sanity-check encodings and value ranges
  2. fetch ESA WorldCover 2020 onto the chip grid (cached to data/interim/worldcover_chips/)
  3. stratify and count pixels per stratum

Writes data/interim/level0_inventory.csv (one row per chip) and prints a
per-event and per-split summary. This is the deliverable that says whether the
flooded-vegetation hypothesis test is powered at all.
"""
import csv
import pathlib
import sys

import numpy as np
import rasterio
from tqdm import tqdm

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog, io, strata  # noqa: E402

OUT_DIR = catalog.DATA / "interim"
WC_DIR = OUT_DIR / "worldcover_chips"
CSV = OUT_DIR / "level0_inventory.csv"


def worldcover_cached(chip_id: str, grid: io.Grid) -> np.ndarray:
    p = WC_DIR / f"{chip_id}_WorldCover2020.tif"
    if p.exists():
        with rasterio.open(p) as src:
            return src.read(1)
    wc = io.worldcover_on_grid(grid, year=2020)
    WC_DIR.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        p, "w", driver="GTiff", height=grid.height, width=grid.width, count=1, dtype="uint8",
        crs=grid.crs, transform=grid.transform, compress="deflate", nodata=0,
    ) as dst:
        dst.write(wc, 1)
    return wc


def main():
    split = catalog.s1f11_split()
    chip_to_split = {c: s for s, cs in split.items() for c in cs}
    chips = catalog.s1f11_hand_chips()
    missing = [c for c in chips if c not in chip_to_split]
    if missing:
        print(f"warning: {len(missing)} chips on disk not in any split (first: {missing[:3]})")

    # Prefetch WorldCover in parallel: the remote COG reads dominate runtime.
    import concurrent.futures as cf

    def prefetch(chip):
        _, _, grid = io.read_s1f11_chip(chip)
        worldcover_cached(chip, grid)

    with cf.ThreadPoolExecutor(8) as ex:
        list(tqdm(ex.map(prefetch, chips), total=len(chips), desc="worldcover"))

    rows = []
    for chip in tqdm(chips, desc="chips"):
        s1, label, grid = io.read_s1f11_chip(chip)
        wc = worldcover_cached(chip, grid)
        st = strata.stratify(label, wc)
        c = strata.counts(st)
        vv, vh = s1[0], s1[1]
        valid = label >= 0
        rows.append({
            "chip": chip,
            "event": catalog.s1f11_event(chip),
            "split": chip_to_split.get(chip, "unassigned"),
            "crs": str(grid.crs),
            "h": grid.height, "w": grid.width,
            "label_values": " ".join(map(str, np.unique(label).tolist())),
            "vv_min": float(vv[valid].min()) if valid.any() else np.nan,
            "vv_max": float(vv[valid].max()) if valid.any() else np.nan,
            "vh_min": float(vh[valid].min()) if valid.any() else np.nan,
            "vh_max": float(vh[valid].max()) if valid.any() else np.nan,
            "wc_nodata_frac": float((wc == 0).mean()),
            **{name: c.get(name, 0) for name in strata.NAMES.values()},
        })

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {CSV} ({len(rows)} chips)")

    # --- summaries ---------------------------------------------------------
    names = [n for n in strata.NAMES.values() if n != "ignore"]

    def summarise(key):
        groups = {}
        for r in rows:
            g = groups.setdefault(r[key], {n: 0 for n in names} | {"chips": 0})
            g["chips"] += 1
            for n in names:
                g[n] += r[n]
        print(f"\n== pixels per {key} ==")
        hdr = f"{key:12s} {'chips':>5s} " + " ".join(f"{n:>16s}" for n in names) + f" {'crop%flood':>10s}"
        print(hdr)
        for k in sorted(groups):
            g = groups[k]
            flood = sum(g[n] for n in names if n.startswith("flood"))
            crop_pct = 100 * g["flood_cropland"] / flood if flood else 0
            print(f"{k:12s} {g['chips']:5d} " + " ".join(f"{g[n]:16,d}" for n in names) + f" {crop_pct:9.1f}%")

    summarise("event")
    summarise("split")

    print("\n== sanity ==")
    print("label value sets seen:", sorted({r["label_values"] for r in rows}))
    print("CRS seen:", sorted({r["crs"] for r in rows})[:5], "...")
    print(f"VV range: {min(r['vv_min'] for r in rows):.1f} .. {max(r['vv_max'] for r in rows):.1f} dB")
    print(f"VH range: {min(r['vh_min'] for r in rows):.1f} .. {max(r['vh_max'] for r in rows):.1f} dB")
    print(f"chips with >10% WorldCover nodata: {sum(r['wc_nodata_frac'] > 0.1 for r in rows)}")


if __name__ == "__main__":
    main()
