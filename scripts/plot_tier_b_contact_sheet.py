"""A contact sheet of all 20 Tier B tiles, so the labeller can see what is in
each one before drawing anything, and so the reviewer can see what the labels
were drawn from.

Per tile, three panels: false colour before, false colour on the event date
(water = black / deep blue), and NDWI on the event date (blue = water). The
percentage is the NDWI water fraction, an indication only -- NDWI is itself an
optical threshold and is not a label.

Output: docs/figures/tier_b_tiles_<n>.png and data/labels/tile_water_hint.csv
"""
from __future__ import annotations

import csv
import pathlib
import sys

import matplotlib
import numpy as np
import rasterio

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog  # noqa: E402

IMG = catalog.DATA / "labels" / "imagery"
FIG = catalog.ROOT / "docs" / "figures"
PER_PAGE = 5


def find(d: pathlib.Path, prefix: str):
    hits = sorted(d.glob(f"{prefix}*.tif"))
    return hits[0] if hits else None


def rgb(path):
    with rasterio.open(path) as s:
        return np.transpose(s.read(), (1, 2, 0))


def main():
    with open(catalog.DATA / "labels" / "optical_availability.csv") as f:
        rows = sorted(csv.DictReader(f), key=lambda r: int(r["label_order"]))
    hints = []
    page, axes, fig = 0, None, None
    for i, r in enumerate(rows):
        if i % PER_PAGE == 0:
            if fig is not None:
                fig.tight_layout()
                fig.savefig(FIG / f"tier_b_tiles_{page}.png", dpi=95, bbox_inches="tight")
                plt.close(fig)
            page += 1
            fig, axes = plt.subplots(PER_PAGE, 3, figsize=(11, 3.4 * PER_PAGE))
        d = IMG / r["tile_id"] / "optical"
        row = axes[i % PER_PAGE]
        for a in row:
            a.set_xticks([])
            a.set_yticks([])
        pre, ev, nd = find(d, "falsecolour_pre"), find(d, "falsecolour_event"), find(d, "ndwi_event")
        frac = float("nan")
        if pre:
            row[0].imshow(rgb(pre))
        row[0].set_ylabel(f"{r['tile_id']}\n{r['stratum']}", fontsize=8)
        row[0].set_title(f"before  {r.get('pre_date', '')}", fontsize=8)
        if ev:
            row[1].imshow(rgb(ev))
        row[1].set_title(f"EVENT  {r.get('event_date', '')}  ({float(r.get('event_clear_frac') or 0):.0%} clear)", fontsize=8)
        if nd:
            with rasterio.open(nd) as s:
                a = s.read(1)
            frac = float((a > 0).mean())
            row[2].imshow(a, cmap="RdYlBu", vmin=-0.4, vmax=0.4)
        row[2].set_title(f"water index — {frac:.0%} water" if nd else "no event optical", fontsize=8)
        hints.append({"tile_id": r["tile_id"], "stratum": r["stratum"], "label_order": r["label_order"],
                      "event_date": r.get("event_date", ""), "event_clear_frac": r.get("event_clear_frac", ""),
                      "ndwi_water_frac": round(frac, 3) if frac == frac else ""})
    if fig is not None:
        fig.tight_layout()
        fig.savefig(FIG / f"tier_b_tiles_{page}.png", dpi=95, bbox_inches="tight")
        plt.close(fig)

    p = catalog.DATA / "labels" / "tile_water_hint.csv"
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(hints[0].keys()))
        w.writeheader()
        w.writerows(hints)
    print(f"wrote {page} contact sheets and {p}")
    for h in hints:
        print(f"  {h['tile_id']:14s} {h['stratum']:11s} clear {float(h['event_clear_frac'] or 0):4.0%}  "
              f"water {h['ndwi_water_frac'] if h['ndwi_water_frac'] != '' else '  -'}")


if __name__ == "__main__":
    main()
