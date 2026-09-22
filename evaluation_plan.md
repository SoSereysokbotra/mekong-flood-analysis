# Evaluation plan — pre-registered

**Status: DRAFT v0.1, 22 September 2026. Not yet frozen.**
Freezing = a dedicated commit titled `Freeze evaluation plan v1` that changes only this status line. No Level 3 training run may be logged before that commit exists; `scripts/level3_train.py` checks `git log` for it and refuses to start otherwise. After freezing, any change is a new version with a dated changelog entry and a written reason, and results are reported against the version that was in force when the run was made.

Every number here comes from `results/experiment_log.csv` and the per-run metrics files it points to (Level 1 commit `d6f4f3a`, Level 2 commit — see git log). Nothing was taken from other projects or from any AI's expectation (plan rule 10).

## 1. Hypothesis

> Thresholding misses flooded vegetation because double bounce makes it bright. A segmentation model using dual-polarisation (VV + VH) and spatial context will recover a meaningful share of flooded-vegetation pixels that thresholding misses, without a material loss of precision on dry cropland.

Level 2 established that per-pixel intensity does **not** separate bright flooded cropland from dry cropland on the training events (AUC 0.51–0.53 on VV, VH and VV−VH). The hypothesis is therefore specifically a claim about **spatial context**, and the experiment includes a per-pixel control to prove that any gain comes from context (§5).

## 2. Data and splits (fixed)

- Benchmark: Sen1Floods11 v1.1, **hand labels only** (`LabelHand`). Otsu-derived and weak labels are never used for evaluation (plan rules 2, 7).
- Split by event (`catalog.s1f11_split()`): train = Bolivia, Ghana, India, Pakistan, Paraguay, Somalia, Sri-Lanka, USA (368 chips); valid = Spain, Nigeria (48); **test = Mekong / Cambodia (30), held out entirely** (rules 5, 8).
- Land type from ESA WorldCover 2020 (`strata.land_type`). Sub-strata: `cropland_bright` / `cropland_dark` / `vegetation_bright` = labelled flood on that land type with VH ≥ / < **−19.65 dB** (the Level 1 train-fit threshold, frozen in `metrics.BRIGHT_VH_DB`).
- Pre-processing: Sen1Floods11 chips as shipped (σ⁰, dB, GEE). The Level 4 Cambodia pipeline (Planetary Computer RTC, γ⁰) is different; the switch effect is measured before any Level 4 conclusion (rule 9, plan §5).

## 3. Baseline (fixed)

`otsu_vh_global`: VH < −19.65 dB, threshold fitted on train, selected on valid by cropland IoU (`experiment_log.csv`, selection row 2026-09-22 06:52, commit `23e93d4`). Its held-out test scores are the reference for every comparison (rule 6):

| Group | IoU | recall | precision | n labelled flood |
| --- | --- | --- | --- | --- |
| all | 0.765 | 0.887 | 0.847 | 1,719,926 |
| cropland | 0.740 | 0.924 | 0.789 | 654,764 |
| **cropland_bright** | — | **0.000** | — | 49,960 |
| cropland_dark | — | 1.000 | — | 604,804 |
| vegetation | — | 0.738 | — | 504,608 |
| **vegetation_bright** | — | **0.000** | — | 132,166 |
| open_water | — | 0.990 | — | 516,519 |

A second, free reference: `otsu_vv_global` (VV < −11.91 dB) reaches `cropland_bright` recall 0.387 and `vegetation_bright` recall 0.435 on test with cropland precision 0.879. **Any model result below these is not an improvement over a second threshold.**

## 4. Metrics (fixed)

Primary: recall on `cropland_bright` and `vegetation_bright`; IoU, recall and precision on `cropland`; IoU on `all`. Overall accuracy is not used (rule 2). All metrics are pixel-pooled over the split (micro), with per-chip recall on `cropland_bright` reported alongside so no single chip can carry the result. Every metric is reported for every land type on every run; nothing is reported pooled-only (rule 1).

## 5. Model selection (fixed) — valid only, never test

Candidates (architecture, inputs, loss, augmentation, epoch) are compared **only on valid**. Selection score on valid:

    score = cropland_bright_recall   if cropland_precision ≥ 0.48   else −1
    tie-break: cropland IoU

(0.48 = valid baseline cropland precision 0.526 minus 0.05.) The selected configuration is written to the log with `record_selection("level3", …)` and committed before the test split is scored. The test split is scored **once per selected model**, and additionally once for each of the fixed controls in §6, never for sweeps.

## 6. Controls that must be run and reported (fixed)

1. `otsu_vh_global` and `otsu_vv_global` (already scored).
2. **Per-pixel control:** logistic regression (or small MLP) on (VV, VH, VV−VH, slope) per pixel, trained on train, selected on valid like any candidate. If the U-Net does not beat this control on `cropland_bright` recall at equal or better cropland precision, spatial context did not help and the hypothesis is not supported regardless of pooled scores.
3. U-Net **VV-only**: isolates the contribution of dual-pol.

## 7. Outcome criteria (the X and Y) — on the held-out Mekong split, selected model only

Let B = `cropland_bright` recall, V = `vegetation_bright` recall, P = cropland precision, I = all IoU, D = `cropland_dark` recall.

| Outcome | Condition |
| --- | --- |
| **Confirmed** | B ≥ **0.50** and V ≥ **0.50** and P ≥ **0.75** and I ≥ **0.765** and D ≥ 0.95, and the model beats the per-pixel control on B by ≥ 0.10 |
| **Partial** | not confirmed, but (B ≥ 0.20 or V ≥ 0.20) with P ≥ 0.75 and I ≥ 0.74 — improvement exists but is small or is bought elsewhere; report *which* conditions (chip, VV-dark vs VV-bright, crop stage) it works in |
| **Rejected** | otherwise — including the case B ≥ 0.50 with P < 0.75 (over-detection), and the case where the U-Net does not beat the per-pixel control |

Why these values (from Level 1–2 results only):
- **X = +50 points on bright recall** (from 0.000): must clearly exceed the 0.387 / 0.435 that a plain VV threshold gets for free, with margin for the 50 k / 132 k pixel sample sizes.
- **Y = cropland precision ≥ 0.75**: baseline is 0.789; a loss of up to ~4 points is accepted as the price of recovering a class the baseline ignores entirely; more than that means the model is buying recall with false alarms on dry fields, the Level 2 FP class that already dominates (59 % of test FP).
- **I ≥ 0.765** and **D ≥ 0.95**: no regression on what thresholding already does well.
- **Per-pixel control margin 0.10**: separates "learned context" from "learned a better threshold".

## 8. What is *not* a valid move after freezing

- Changing any threshold in §7 after seeing a test number.
- Choosing which control to report, or which chips to include, after seeing test numbers.
- Reporting a valid score as if it were a test score.
- Presenting the Sen1Floods11 Mekong result as a result about Cambodian rice at harvest stage: the test scene is 5 Aug 2018 (vegetative rice). That claim needs Level 4 with Tier B labels (`data/labels/LABELLING_PROTOCOL.md`). Level 3 answers whether spatial-context models recover bright flooded vegetation on the benchmark; Level 4 answers whether that transfers to Cambodian rice in October.

## Changelog

- v0.1 — 22 Sep 2026 — draft from Level 1–2 results; awaiting freeze.
