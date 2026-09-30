# Mekong Flood Intelligence

SAR-based flood detection for Cambodia, targeting flooded rice fields — the case
that operational radar flood maps are documented to miss (double-bounce makes
flooded vegetation *bright*, inverting the "dark = water" rule).

- **Start here:** [docs/SUMMARY.md](docs/SUMMARY.md) — the whole project in 5 minutes; [docs/PROJECT_REPORT.md](docs/PROJECT_REPORT.md) — everything in one file
- Project plan: [Mekong Flood Intelligence.md](Mekong%20Flood%20Intelligence.md)
- Data access record (Step 0): [step0_data_access.md](step0_data_access.md)

## Check any date: is the province flooded?

```
python scripts/check_flood.py --date 2026-10-15     # or no --date for the newest radar image
```

Finds the Sentinel-1 pass on that date and one 18 days before, maps new water with the three methods, compares with the same dates in the previous 3 years, and writes `results/check/<date>/report.md` + `map.png`. Each pass is ~350 MB, so on a slow connection use Colab: `notebooks/colab_check_flood.ipynb` (type the date, Run all). Reproduces the Level 4 numbers exactly for 14 Oct 2020.

## Setup (Windows, Python 3.10, RTX 3050)

```
python -m venv .venv
.venv\Scripts\python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126
.venv\Scripts\python -m pip install -e ".[ml,dev]"
.venv\Scripts\python scripts/download_sen1floods11.py      # ~1.7 GB hand-labelled benchmark
```

## Layout

```
data/aoi/          study-area polygon (tracked)
data/raw/          downloaded inputs (ignored)
data/interim/      derived rasters, chips, strata (ignored)
data/labels/       Tier B hand labels + labelling protocol
src/mfi/           library code
  catalog.py       where every input lives (STAC queries, Sen1Floods11 paths, event split)
scripts/           one-off CLI utilities
configs/           experiment configs (one per Level 3 run)
notebooks/         exploration, numbered by level
evaluation_plan.md written and committed at end of Level 2, before any training
```

## Rules the code enforces

- Test only on hand-made labels (`LabelHand`). Otsu-derived layers are never labels.
- Split by event: all Cambodia ("Mekong") chips are held out. See `catalog.s1f11_split()`.
- One pre-processing pipeline (Planetary Computer RTC, gamma-nought to dB). Any pipeline switch is measured, not assumed.
- Every score is reported per land-type stratum (WorldCover), never pooled only.
