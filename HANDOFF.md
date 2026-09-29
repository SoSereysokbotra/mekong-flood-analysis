# Handoff — Mekong Flood Intelligence

**Read this first in a new session.** Written 29 September 2026, at commit `b5adfbc`.
Repo: https://github.com/SoSereysokbotra/mekong-flood-analysis (branch `main`, everything pushed).

---

## 1. What the project is

Detect flooded rice fields in Cambodia from Sentinel-1 radar, targeting the case operational flood maps are documented to miss: double-bounce scattering makes flooded rice look **bright**, inverting the "dark = water" rule that thresholding relies on.

Plan: `Mekong Flood Intelligence.md`. Owner and labeller: Sobotra (year-2 student).

## 2. Where it stands

**Step 0 through Level 4 are complete.** The plan itself says that is a complete, defensible project; Levels 5–7 are stretch goals.

| Level | Status | Key result |
| --- | --- | --- |
| Step 0 | done | Data access confirmed. Track **164 descending** covers the province and passes on the 14 Oct peak (orbit 26 does **not** cover it). |
| 0 | done | Sen1Floods11 inventory. Flooded cropland is the largest flood stratum in the held-out Cambodia set (654k px, 38 %). |
| 1 | done | Threshold baseline. `otsu_vh_global` (VH < −19.65 dB). **Bright flooded cropland is rare in the Aug-2018 Cambodia labels (7.6 % above the pre-registered VH threshold; 2.3 % as bright as dry cropland)** — the test scene is vegetative-stage rice. |
| 2 | done | Failure analysis. Per-pixel intensity **cannot** separate bright flooded cropland from dry cropland (AUC ≈ 0.5) → only spatial context can help → a per-pixel control is mandatory. |
| 3 | done | Hypothesis **CONFIRMED** twice: under plan v1.0 (σ⁰) and again under v1.1 (RTC γ⁰). Selected model `unet_vvvh_cropw`. |
| 4 | done | Cambodia flood maps + seasonal baseline + **scored against Tier B hand labels**. |
| 6 (minimal) | done | `scripts/check_flood.py --date YYYY-MM-DD`: flood check for any date, vs the previous 3 years. Colab: `notebooks/colab_check_flood.ipynb`. Verified: reproduces Level 4 exactly for 14 Oct 2020. Radar exists to 26 Sep 2026; track 164 now every 6 days (S1A/C/D). **S1C/S1D were never tested against labels.** |
| — | first real use | **26 Sep 2026: UNUSUAL FLOODING**, 1,998 km² flooded cropland (range 1,326–1,998), 3.8–6.3× the same dates in 2023–2025, all 3 methods agree (`results/check/2026-09-26/`). Matches the news: late-Sep 2026 floods, Banteay Meanchey among the worst-hit provinces. S1D built-up brightness is within the normal range and slightly brighter, so a calibration artefact would hide water, not invent it. Mapped area exceeds official figures (~500 km² of rice across 10 provinces, as of 28 Sep), as in 2020. |
| 7 | done | Flood report per district, generated from artefacts (`docs/level7_report.md`, `scripts/level7_report.py`). 3 districts = 84 % of flooded cropland. |

### The headline numbers

**Level 3, held-out Cambodia chips, plan v1.1 (`docs/level3_results_v11.md`):** selected model bright-cropland recall **0.790**, bright-vegetation **0.754**, cropland precision **0.827**, all-IoU 0.797. Per-pixel control 0.239. Every frozen criterion passed.

**Level 4, Banteay Meanchey, 14 Oct 2020 (`docs/level4_cambodia.md`):** flood at peak 882 / 1,131 / **1,218 km²** (threshold / VV-only U-Net / selected). The 2020 event is **3.9–6.0× the median of 2018/2019/2021/2022** — a real flood, not normal paddy ponding.

**Level 4 scored on Sobotra's own labels (`docs/level4_tierb_scores.md`) — the project's payoff:** on cropland, total water IoU **0.713** (selected) vs 0.498 (threshold), recall **0.801** vs 0.553, at the same precision. The benchmark ranking of the three methods transfers to Cambodia.

## 3. The one open scientific gap

The Tier B labels were seeded from an **optical** water index (NDWI) and human-filtered. Optical cannot see water under a closed rice canopy — **which is exactly the case the project is about**. So:

- What is proven: the model finds more *optically visible* flooding than thresholding, on Cambodian ground.
- What is **not** proven: that it finds flooding *hidden under the canopy*. Flooded-vegetation recall against these labels is not a fair test and must not be quoted as evidence either way.

Closing this needs a labeller adding polygons where they believe water exists under canopy, from terrain and hydrology rather than from the image. That is the single most valuable remaining piece of science.

**Checked 29 Sep 2026 (`docs/level4_tierb_scores.md` §5): not closable with free data here.** The cropland is flat to within DEM noise (median 1.5 m spread per tile), and post-event optical shows almost no green-then-water fields (0.001 km² on cropland). Only independent evidence (L-band ALOS-2, field reports) could close it.

## 4. What the user chose to do next

Offered four options; they were about to choose when the session ended:

- **A. Write it up** — one 5-minute summary tying the 12 documents together. *Recommended: highest value, least work.*
- **B. Level 7 intelligence report** — the decision-useful output in the plan (area flooded, of which cropland, with its own stated limitation).
- **C. Close the gap in §3** — hardest, most valuable scientifically, needs hours of the user's judgement.
- **D. Level 6 automation** — the plan calls this a separate software project.

**Option A chosen and done (29 Sep 2026): `docs/SUMMARY.md`.** Option C was attempted and found not feasible with free data (see §3). B (Level 7 report) is done: `docs/level7_report.md`. Remaining: D (Level 6 automation), or independent hidden-water evidence. Ask before starting either. Do not assume.

## 5. How to work in this repo

### Rules that are not negotiable
- **Commits carry no AI attribution.** See `CLAUDE.md`. Author is Sobotra.
- **Never select anything from test scores.** Selection happens on valid, is recorded in `results/experiment_log.csv` as a `selection` row, and is committed *before* test is scored. `scripts/level3_test.py` enforces this.
- **Every number lives in an artefact** (`results/**/*.json|csv`) and documents quote them. If a doc disagrees with a file, the file wins.
- `evaluation_plan.md` is **FROZEN v1.1**. Changes need a new version with a dated changelog and a written reason.
- The user's own list of past mistakes is in `Mistake_avoidance.md`. Honour it.

### Environment
- Windows, `.venv\Scripts\python`, CUDA torch, RTX 3050 4 GB.
- **The home connection to Azure is ~100 KB/s.** Anything that downloads more than ~50 MB must run on Colab.
- `MFI_PIPELINE=rtc` (default) uses the RTC γ⁰ chips and writes to `results/level3_rtc`; `sigma0` reproduces the v1.0 results in `results/level3`.

### Colab
Notebooks are two-cell launchers; all logic is in repo scripts, because **Colab caches notebooks aggressively** and stale cells caused three failed runs.
- Training: `notebooks/colab_v11.ipynb` → `scripts/colab_run.py`
- Level 4 inference: `notebooks/colab_level4.ipynb` → `scripts/colab_level4.py` (`--normal-years` for the seasonal baseline)
- Needs in Drive `MyDrive/mfi/`: `chip_cache_rtc.zip`, `level3_rtc_checkpoints.zip`
- `GITHUB_TOKEN` must be **exported in a notebook cell** — a subprocess cannot read Colab secrets.

### Traps already hit (do not repeat)
- Reading remote COGs: never `WarpedVRT` over a large grid, never `boundless=True`, never `read_masks` with `out_shape` — all three bypass the overview pyramid and turn seconds into 20 minutes. Use the decimated windowed read in `src/mfi/rtc.py`.
- Planetary Computer STAC rate-limits per-chip searches: search once per event.
- Colab has NumPy 2 and no raw GeoTIFFs; code must not assume either.
- JRC "permanent water" is only 10 km² in this province, so Tier D is useless here — the pre-event subtraction does that job instead.

## 6. Map of the repo

```
Mekong Flood Intelligence.md   the plan (the user's own document)
Mistake_avoidance.md           the user's 8 rules from a previous project
evaluation_plan.md             FROZEN v1.1 — the pre-registered criteria
CLAUDE.md                      commit conventions and standing rules
HANDOFF.md                     this file
docs/SUMMARY.md                5-minute write-up of the whole project
docs/level7_report.md          the flood report (generated; edit the script, not the file)

docs/
  level0_inventory.md          dataset inventory, powered-ness of the test
  level1_baseline.md           threshold baseline, the bright-rice finding
  level2_failure_analysis.md   why thresholding fails, separability AUC
  level3_results.md            v1.0 (σ⁰) — confirmed; kept for the record
  level3_results_v11.md        v1.1 (RTC) — confirmed; the live result
  level4_pipeline_switch.md    why v1.0 models could not be used on Cambodia
  level4_cambodia.md           the flood maps, Tier D/E, seasonal baseline
  level4_tierb_scores.md       scored on the hand labels — the payoff
  *_explained_simple.md        plain-language explainers the user asked for
  figures/                     every figure, all generated from artefacts

src/mfi/       catalog, io, rtc, data, models, metrics, strata, infer, experiments
scripts/       one per step; level3_train/test, level4_*, fetch_*, plot_*
results/       experiment_log.csv + per-run metrics; the single source of numbers
data/labels/   LABELLING_PROTOCOL.md (FROZEN v1.2), tiles.geojson,
               tierB_bmc_oct2020.gpkg (199 polygons, 95 confirmed), review.html
```

## 7. Working with this user

- Keep replies **short**. Long messages frustrate them; they have said so directly.
- They are new to GIS and to remote sensing. Explain in plain words, one step at a time, and give exact file paths and exact buttons.
- They cannot always tell what a satellite image shows — give them the rule ("deep navy = water, white = cloud") rather than assuming.
- When they are stuck on a tool, question whether the tool is right. QGIS digitising was replaced by a browser review page (`scripts/make_review_page.py`) and the 116-candidate review then took one session.
- They ask a second AI (Gemini) to audit the work. That has been useful — it caught real bugs. Treat its findings on merit, verify them, and say so when it is wrong.
