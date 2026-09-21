# Mekong Flood Intelligence

SAR-based flood detection for Cambodia, targeting flooded rice fields — the case
that operational radar flood maps are documented to miss (double-bounce makes
flooded vegetation *bright*, inverting the "dark = water" rule).

- Project plan: [Mekong Flood Intelligence.md](Mekong%20Flood%20Intelligence.md)
- Data access record (Step 0): [step0_data_access.md](step0_data_access.md)

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
