# Level 1 — Thresholding baseline, scored per land type

**Date:** 22 September 2026
**Runs:** `results/experiment_log.csv`, level `level1`; per-run artefacts under `results/level1/<method>/`
**Scripts:** `scripts/level1_threshold.py` (scores), `scripts/level1_label_brightness.py` (label check), `scripts/plot_level1.py` (figures from artefacts)
**Figures:** `docs/figures/level1_scores.png`, `docs/figures/level1_brightness.png`

All numbers below are copied from `results/level1/*/metrics_*.json` and `results/level1/label_brightness.json`. If a number here disagrees with those files, the files are right.

## Procedure

1. Split by event (commit `23e93d4`): train = 8 events, 368 chips; valid = Spain + Nigeria, 48 chips; test = Mekong, 30 chips. No chip or event is shared.
2. Global Otsu thresholds fitted on train only: **VV −11.91 dB, VH −19.65 dB** (`results/level1/_global_thresholds/config.json`).
3. Five methods scored on train and valid. Selection on valid by **cropland IoU among the project's own methods** → `otsu_vh_global`. Recorded in the log at 06:52 and committed *before* any test row existed.
   - The first selection row (06:51) used cropland recall alone; it was superseded within a minute because recall alone rewards over-detection. Both rows are kept. Same method either way.
4. `--test` scored the 30 Mekong chips once, for every method. No decision was made from test numbers.

`authors_otsu` (the dataset's `S1OtsuLabelHand` layer) is a cross-check, not a candidate: it agrees 92–95 % with a per-event VH threshold from the dataset metadata, i.e. a threshold fitted on each *whole scene* — including the Mekong test scene.

## Scores (selected method in bold)

### Valid — Spain + Nigeria

| Method | all IoU | cropland IoU | cropland recall | cropland precision | open-water recall | vegetation recall |
| --- | --- | --- | --- | --- | --- | --- |
| otsu_vh_perchip | 0.264 | 0.332 | 0.743 | 0.375 | 0.745 | 0.421 |
| otsu_vv_perchip | 0.252 | 0.297 | 0.742 | 0.331 | 0.941 | 0.489 |
| **otsu_vh_global** | **0.462** | **0.490** | **0.877** | **0.526** | **0.985** | **0.650** |
| otsu_vv_global | 0.388 | 0.404 | 0.847 | 0.435 | 0.987 | 0.752 |
| authors_otsu (cross-check) | 0.658 | 0.646 | 0.691 | 0.908 | 0.943 | 0.481 |

### Test — Mekong, held out

| Method | all IoU | cropland IoU | cropland recall | cropland precision | open-water recall | vegetation recall |
| --- | --- | --- | --- | --- | --- | --- |
| otsu_vh_perchip | 0.493 | 0.589 | 0.848 | 0.658 | 0.954 | 0.569 |
| otsu_vv_perchip | 0.505 | 0.634 | 0.872 | 0.698 | 0.985 | 0.657 |
| **otsu_vh_global** | **0.765** | **0.740** | **0.924** | **0.789** | **0.990** | **0.738** |
| otsu_vv_global | 0.754 | 0.818 | 0.921 | 0.879 | 0.993 | 0.815 |
| authors_otsu (cross-check) | 0.780 | 0.816 | 0.842 | 0.964 | 0.982 | 0.551 |

**The baseline the plan's rule 6 refers to is `otsu_vh_global` on test: cropland IoU 0.740, cropland recall 0.924, cropland precision 0.789.** `otsu_vv_global` scores higher on test cropland IoU (0.818) but was not selected on valid; it is reported, not adopted.

## Findings

### 1. Thresholding does *not* miss flooded cropland in the Cambodia hand labels

Cropland recall 0.92 is within 7 points of open-water recall 0.99. The 8 % of flooded-cropland pixels that thresholding misses on test is ~50 k pixels out of 655 k.

### 2. Bright flooded cropland is nearly absent from the Cambodia labels (Mistake_avoidance #8)

From `results/level1/label_brightness.json`, VH band:

| Split | Flooded-cropland px | Flood median | Dry-cropland median | Above threshold | At/above dry median |
| --- | --- | --- | --- | --- | --- |
| train | 1,887,610 | −21.2 dB | −16.8 dB | 34.7 % | **16.8 %** (~317 k px) |
| valid | 765,131 | −26.8 dB | −17.2 dB | 11.7 % | 5.1 % |
| **test (Mekong)** | 654,764 | −28.8 dB | −16.2 dB | 7.3 % | **2.3 %** (~15 k px) |

In the Aug 2018 Cambodia scene, labelled flooded cropland is a single dark mode at −29 dB (`level1_brightness.png`, right panel) — young or fully submerged paddy, the "water dominates" condition. There is no bright mode. The training events (India, Pakistan, Somalia…) *do* contain a substantial population of flooded cropland as bright as dry cropland.

**What this means for the hypothesis (Section 6 of the plan):** the hypothesis is about pixels that thresholding misses because double bounce makes them bright. On the Sen1Floods11 Cambodia labels there are ~15–48 k such pixels, spread over 30 chips. That is enough to *report* a recall number for a "bright flooded cropland" sub-stratum, but not enough for a confident confirmed/rejected verdict, and the labels may themselves under-represent bright flooded rice (analysts labelled from S1 + S2; bright radar pixels are exactly where a labeller is tempted to say "not water").

### 3. Per-chip Otsu is a poor baseline; per-event / global thresholds are the real competitor

Per-chip Otsu splits every chip's histogram in two even when the chip has no water, so precision collapses on dry chips (valid cropland precision 0.33–0.38). Any Level 3 comparison against "Otsu" must be against the global threshold, or the improvement is an artefact.

### 4. Precision–recall trade-off is one threshold away

The authors' lower per-event thresholds (Spain −25.1, Nigeria −21.9) buy cropland precision 0.91–0.96 at the cost of recall 0.69–0.84. The choice of X (recall gain) and Y (precision floor) at Level 2 must be made knowing this: a model that "improves recall" by 5 points is worthless if a 2 dB threshold shift does the same.

### 5. Route A adopted: the `cropland_bright` sub-stratum (added 22 Sep, backfilled from saved predictions)

`metrics.py` now scores two sub-strata on every run: `cropland_bright` = labelled flood ∧ cropland ∧ VH ≥ −19.65 dB (the frozen Level 1 threshold), and `cropland_dark` = the rest. They contain only labelled-flood pixels, so read their **recall**; precision is undefined. From `results/level1/<method>/metrics_<split>.json` after `scripts/level1_bright_backfill.py`:

| Method | bright recall — train (n = 677,618) | valid (n = 94,295) | **test (n = 49,960)** |
| --- | --- | --- | --- |
| otsu_vh_perchip | 0.315 | 0.124 | 0.117 |
| otsu_vv_perchip | 0.376 | 0.236 | 0.211 |
| **otsu_vh_global (baseline)** | **0.000** | **0.001** | **0.000** |
| otsu_vv_global | 0.241 | 0.396 | **0.387** |
| authors_otsu | 0.067 | 0.114 | 0.142 |

Two things to carry into Level 2 and 3:
- The baseline's bright recall is 0 *by construction* (its dark recall is 1.000, which is the sanity check). Any Level 3 gain on `cropland_bright` is therefore measured against zero, and must be paired with dry-cropland precision so it cannot be bought by over-detection.
- A VV threshold recovers 39 % of VH-bright flooded cropland on test. Some double-bounce pixels are bright in VH but still dark in VV: the two polarisations disagree exactly where the hypothesis lives. This is the measured, not assumed, reason to give Level 3 both bands.

## Implications for the plan — decision after Level 1 (Route A adopted; B protocol and C to follow)

Three routes, not mutually exclusive:

- **A. Keep the Sen1Floods11 test as is** and add a `bright_flooded_cropland` sub-stratum (flood & cropland & VH ≥ global threshold) to every score. Cheap; honest; weak statistical power on Cambodia (~48 k px). Recommended as a minimum.
- **B. Tier B hand labels on the Oct 2020 event, targeting mature rice.** The Aug 2018 scene is mid-season; October is 1–2 months before harvest, when rice is tall and double bounce is strongest. This is the only route that directly tests the plan's motivating case, and the labelling protocol must instruct labelling from optical / ancillary evidence, not from radar darkness — otherwise the labels inherit the bias. Requires a human labeller (you).
- **C. Train on the bright population in train events** (India, Pakistan, Somalia) and report the bright sub-stratum on valid, where 5 % (~39 k px) exist. Tests whether a model can learn the bright case at all, independent of Cambodia.

## Level 1 deliverable check

- [x] Flood map + scores, split by land type (Section 7, Level 1)
- [x] Baseline for rule 6 fixed: `otsu_vh_global`, test cropland IoU 0.740 / recall 0.924 / precision 0.789
- [x] Selection on valid recorded and committed before test was scored
- [x] Predictions saved per chip (`results/level1/<method>/pred/`, git-ignored) for Level 2 failure analysis
- [x] Key assumption measured (Mistake_avoidance #8): bright flooded cropland is 2.3 % of Cambodia test flood-cropland labels
