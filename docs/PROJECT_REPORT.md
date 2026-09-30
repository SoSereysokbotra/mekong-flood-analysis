# Mekong Flood Intelligence: full project report

**Author:** Sobotra · **Period:** 21–30 September 2026 · **Repository:** https://github.com/SoSereysokbotra/mekong-flood-analysis

This file covers the whole project in one place: what was built, what was found, every main result, and where each output lives. The numbers are copied from the results files under `results/`. If a number here ever disagrees with those files, the files are correct.

**Shorter versions:** [SUMMARY.md](SUMMARY.md) (5 minutes) · [level7_report.md](level7_report.md) (the flood report for decision-makers)

---

## Contents

1. [The project in one paragraph](#1-the-project-in-one-paragraph)
2. [The problem](#2-the-problem)
3. [Rules the project followed](#3-rules-the-project-followed)
4. [Timeline](#4-timeline)
5. [Level by level: what was done and found](#5-level-by-level-what-was-done-and-found)
6. [The Cambodia test: October 2020](#6-the-cambodia-test-october-2020)
7. [The flood report (Level 7)](#7-the-flood-report-level-7)
8. [The flood-check tool, and its first real use: September 2026](#8-the-flood-check-tool-and-its-first-real-use-september-2026)
9. [Limits: what this project does not show](#9-limits-what-this-project-does-not-show)
10. [Reviews and corrections](#10-reviews-and-corrections)
11. [Every output, and where it is](#11-every-output-and-where-it-is)
12. [How to run it](#12-how-to-run-it)
13. [What could come next](#13-what-could-come-next)
14. [Glossary](#14-glossary)

---

## 1. The project in one paragraph

The project detects flooded rice fields in Cambodia from free satellite radar (Sentinel-1). Normal radar flood maps miss flooded rice, because tall rice makes flood water look **bright** instead of dark. An AI model (a U-Net) was trained on floods in other countries and tested under rules written down before training. It found the bright flooded fields that a simple threshold misses. It was then checked on Cambodian ground against labels drawn by hand for the October 2020 flood in Banteay Meanchey province. There it found **80 %** of the visible flood water on farmland, against **55 %** for the usual method, at the same precision. The project produced a district-level flood report and a tool that checks any date. The tool's first real use found **unusual flooding in Banteay Meanchey on 26 September 2026**, confirmed by the news.

---

## 2. The problem

**How radar sees water.** The satellite sends a radio pulse and measures how much comes back.

| Ground | What happens to the pulse | How it looks |
| --- | --- | --- |
| Dry field | Rough soil scatters it; some comes back | grey |
| Open flood water | Flat water reflects it away, like a mirror | **dark** |
| Flooded tall rice | Pulse hits the water, bounces off the stems, comes back ("double bounce") | **bright**, like dry land |

The standard method (a *threshold*) says "dark = water". It therefore misses flooded rice, the flood that matters most to Cambodian farmers. More background: [radar_physics_explained_simple.md](radar_physics_explained_simple.md).

**The hypothesis**, written down before any model was trained: *a model that uses spatial context (the shape and surroundings of a field) can recover bright flooded cropland that a threshold misses, without gaining it by over-detecting dry fields.*

---

## 3. Rules the project followed

These come from the plan ([Mekong Flood Intelligence.md](../Mekong%20Flood%20Intelligence.md)) and from lessons of a previous project ([Mistake_avoidance.md](../Mistake_avoidance.md)). The code enforces them.

1. **Test only on hand-made labels.** Labels made by another algorithm are never used as truth.
2. **Cambodia is held out.** No Cambodian image was used in training. The split is by flood event, never by image tile.
3. **Pass criteria are fixed before training** ([evaluation_plan.md](../evaluation_plan.md), frozen and committed on 22 Sep 2026). The commit dates prove the order.
4. **Choose models on validation data only.** The choice is logged and committed before the test set is scored, and `scripts/level3_test.py` refuses to run otherwise.
5. **Every score is split by land type** (cropland, vegetation, open water, built-up), never only one pooled number.
6. **One pre-processing pipeline.** When it had to change, the effect was measured, not assumed.
7. **Every number comes from a results file**, and every figure is generated from one.

---

## 4. Timeline

64 commits, 21–30 September 2026. `git log --oneline` reads as the timeline.

| Date | Milestone |
| --- | --- |
| 21 Sep | Step 0: data access confirmed. Level 0: dataset inventory. First independent review: 9 bugs found and fixed |
| 22 Sep | Level 1 threshold baseline. Level 2 failure analysis. **Evaluation plan frozen.** Level 3 training (local GPU + Colab). **Hypothesis confirmed (plan v1.0).** Pipeline switch measured: the model broke on a different radar product. Plan v1.1: everything rebuilt on one pipeline. **Hypothesis confirmed again** |
| 23 Sep | Level 4: flood maps of Banteay Meanchey, October 2020. Normal-year comparison 2018–2022. Labelling protocol frozen |
| 24 Sep | Hand-label imagery fetched; candidate polygons drawn from optical photos |
| 29 Sep | Hand labels reviewed in a browser page (116 candidates). **Level 4 scored on Cambodian labels.** Summary written. Hidden-water check. Level 7 flood report. Second review (Gemini) and fixes. Flood-check tool built. **26 Sep 2026 flood detected** |
| 30 Sep | Tool fixes after first use in Colab. This report |

---

## 5. Level by level: what was done and found

### Step 0: Can we get the data?

**Yes.** Sentinel-1 radar is free on Microsoft Planetary Computer, already processed (RTC). Track **164 descending** covers the whole province and passed on the 14 Oct 2020 flood peak. Track 26, the first candidate, does not cover it. Record: [step0_data_access.md](../step0_data_access.md).

### Level 0: The training dataset

**Sen1Floods11**: 446 hand-labelled radar tiles from 11 flood events. Split by event:

| Split | Events | Tiles | Flooded cropland pixels |
| --- | --- | --- | --- |
| Train | 8 events | 368 | 1,887,610 |
| Validation | Spain, Nigeria | 48 | 765,131 |
| **Test** | **Mekong (Cambodia), held out** | 30 | **654,764** |

Flooded cropland is the **largest** flood class in the Cambodia test set (38 % of flood pixels), so the test has enough data. Doc: [level0_inventory.md](level0_inventory.md). Figure: [level0_mekong_chip.png](figures/level0_mekong_chip.png).

### Level 1: The baseline (the method to beat)

A single VH threshold, **−19.65 dB**, fitted on training events only (`otsu_vh_global`), was chosen on validation.

| Held-out Cambodia test | All IoU | Cropland IoU | Cropland recall | Cropland precision |
| --- | --- | --- | --- | --- |
| VH threshold | 0.765 | 0.740 | 0.924 | 0.789 |

**Surprise finding:** the Cambodian test scene (5 Aug 2018) has little *bright* flooded rice. Only **7.6 %** of its flooded cropland is above the threshold, and only 2.3 % is as bright as dry cropland. It is young rice, so the water dominates and looks dark. The training events have much more bright flooded cropland. This is why a second Cambodian test (Level 4, October, tall rice) was needed.

Doc: [level1_baseline.md](level1_baseline.md). Figures: [level1_scores.png](figures/level1_scores.png), [level1_brightness.png](figures/level1_brightness.png).

### Level 2: Why the threshold fails

- **On the Cambodia test, 94 % of what the threshold misses is flooded vegetation** (cropland plus trees/grass): 182,000 pixels.
- **Brightness alone cannot separate the two.** On the training events, bright flooded cropland and dry cropland have AUC ≈ 0.5 on every radar band, which is no better than a coin toss. (On the Cambodia test chips it is 0.67–0.72: better, still weak.)
- **Conclusion:** only *spatial context* (what surrounds a pixel) can help. A per-pixel model was therefore added as a control, to prove that any gain really comes from context.
- **Crop calendar:** August rice is young (dark when flooded); October rice is tall (bright when flooded). So October 2020 is the right test month.

Doc: [level2_failure_analysis.md](level2_failure_analysis.md). Figures: [level2_taxonomy.png](figures/level2_taxonomy.png), [level2_joint.png](figures/level2_joint.png), [level2_examples.png](figures/level2_examples.png).

### Level 3: The hypothesis test

Eight models trained, chosen on validation, and the test scored **once**.

**Selected model: `unet_vvvh_cropw`**, a U-Net (1.9 M parameters) using both radar bands (VV + VH), with flooded cropland and vegetation weighted ×4 in training.

**Result on the held-out Cambodia test (plan v1.1):**

| Criterion | Required | Result | |
| --- | --- | --- | --- |
| Bright flooded cropland recall | ≥ 0.50 | **0.790** | pass |
| Bright flooded vegetation recall | ≥ 0.50 | **0.754** | pass |
| Cropland precision | ≥ 0.75 | **0.827** | pass |
| All-water IoU | ≥ 0.765 | **0.797** | pass |
| Dark flooded cropland recall | ≥ 0.95 | **0.997** | pass |
| Beats the per-pixel control by ≥ 0.10 | — | 0.790 vs 0.239 | pass |

**All six criteria passed, so the hypothesis is confirmed on the benchmark.** What the comparisons show:
- **Spatial context works:** the per-pixel model on the same inputs reaches only 0.239.
- **Both radar bands matter:** VV only 0.628 → VV+VH 0.790.
- **The weighted training is decisive:** it beat the 7 other U-Net setups on validation.
- **The verdict is robust:** it also passes under the alternative definition of "bright" (0.716 / 0.730).

**The pipeline lesson.** The first confirmed model (plan v1.0) was trained on a different radar product. On the product used for Cambodia, its accuracy fell from 0.820 to **0.138**. That was measured *before* anything was claimed about Cambodia. Everything was then rebuilt and retrained on one product (plan v1.1), and the hypothesis was confirmed again. Doc: [level4_pipeline_switch.md](level4_pipeline_switch.md).

Docs: [level3_results_v11.md](level3_results_v11.md) (live), [level3_results.md](level3_results.md) (v1.0, kept for the record). Figures: [level3_rtc_test.png](figures/level3_rtc_test.png), [level3_rtc_valid.png](figures/level3_rtc_valid.png), [level3_rtc_per_chip.png](figures/level3_rtc_per_chip.png).

**Known weakness:** the selected model over-detects. It has about 4× the cropland false positives of the VV-only model. **Use it for cropland; use the VV-only U-Net for a general flood map.**

---

## 6. The Cambodia test: October 2020

### The flood maps

Banteay Meanchey province, Sentinel-1 track 164: 26 Sep (before), **14 Oct (peak)**, 1 Nov (after). Radar covered 100 % of the province on all three dates. Flood = water on the date that was not water before.

| Method | Flood at peak | of which cropland | Flooded on 1 Nov |
| --- | --- | --- | --- |
| VH threshold | 882 km² | 815 km² | 823 km² |
| U-Net VV only | 1,131 km² | 1,013 km² | 1,108 km² |
| **U-Net VV+VH (selected)** | **1,218 km²** | **1,113 km²** | 1,072 km² |

![Flood map, 14 Oct 2020](figures/level4_flood_map.png)

### Was it a real flood, or normal wet-season paddy water?

The same track and dates in 2018, 2019, 2021 and 2022 were processed identically. Flooded cropland in 2020 is **3.9–6.0× the median of those four years**. One exception: the VV-only U-Net finds 2022 about as large (1,070 vs 1,013 km²), so the *size* of the anomaly is uncertain, but its existence is not. Figure: [level4_normal_years.png](figures/level4_normal_years.png).

### Scored on hand labels (Tier B)

- **Grid:** 20 squares of 2 × 2 km, chosen by land type *without looking at any model output*.
- **Labels:** candidate water shapes were pre-drawn from Sentinel-2 optical photos (no radar, no model). Sobotra reviewed all 116 in a browser page: 95 accepted, 21 rejected.
- **Scored:** 17 squares (3 had no usable photo).

| Cropland, total water on 14 Oct | VH threshold | VV-only U-Net | **Selected U-Net** |
| --- | --- | --- | --- |
| IoU | 0.498 | 0.612 | **0.713** |
| Recall | 0.553 | 0.669 | **0.801** |
| Precision | 0.835 | 0.879 | 0.867 |

The selected model finds **about 45 % more flooded cropland** than the threshold at the same precision. The benchmark ranking of the three methods holds on Cambodian ground. The same holds on *new flood only* (peak minus before), where the model scores recall 0.735 and precision 0.894, against a threshold recall of 0.533.

Other land types: open water IoU 0.95 for all methods. On vegetation, only 2–4 % of what the methods mapped could be confirmed, which is not usable. Built-up has too few labelled pixels (220) to score.

Docs: [level4_cambodia.md](level4_cambodia.md), [level4_tierb_scores.md](level4_tierb_scores.md). Labels: `data/labels/tierB_bmc_oct2020.gpkg`, protocol [LABELLING_PROTOCOL.md](../data/labels/LABELLING_PROTOCOL.md) (frozen v1.2).

### Can water hidden under the rice be labelled? Measured: no, not with free data

The hand labels come from optical photos, which cannot see under a closed rice canopy. Two free routes were tested (`scripts/level4_hidden_water_feasibility.py`):
- **Elevation map:** the farmland is flat to within **1.5 m** per 2 km square, which is the same as the elevation map's own error. It cannot tell a flooded field from a dry one.
- **November photos:** almost no field was green on the flood date and water later (0 km² on cropland). This test is weak anyway, because receding floods rarely reappear as open water.

So the core question, *does the model find water hidden under the canopy on Cambodian rice?*, **cannot be answered with free data at this site**. Details: [level4_tierb_scores.md §5](level4_tierb_scores.md).

---

## 7. The flood report (Level 7)

A report a non-technical person can act on. It is generated by a script from the results files, so no number in it is typed by hand. Full report: [level7_report.md](level7_report.md).

```
Flood event — Banteay Meanchey province, Cambodia
Detected:                  14 Oct 2020
Flooded area:              1,218 km²   (range 882–1,218)
  of which cropland:       1,113 km²   (range 815–1,113) = 21 % of the province's cropland
Compared with normal:      6.0× the median of four other Octobers (range 3.9–6.0×)
Known limitation:          on cropland it found 74 % of the new flood water people could see
                           in photos; 89 % of what it called flood was flood.
                           Water hidden under the rice canopy is NOT checked.
```

**Three districts held 84 % of the flooded cropland:** Mongkol Borei (469 km²), Preah Netr Preah (340 km²) and Serei Saophoan (123 km²). All three methods rank the same four districts at the top, in the same order.

![Districts 2020](figures/level7_districts.png)

---

## 8. The flood-check tool, and its first real use: September 2026

### The tool

One command answers *"is Banteay Meanchey flooded on this date?"* for any date with a radar image:

```
python scripts/check_flood.py --date 2026-09-26
```

1. It finds the radar pass on that date and one 18 days earlier.
2. It runs all three methods over the whole province.
3. It compares with the same dates in the previous 3 years.
4. It writes a verdict, a map, a district table and a plain-language report.

**Verdict rule:** "unusual flooding" means flooded cropland is more than 2× the usual amount *and* more than 50 km². The rule was not tuned on any event.

**Verified:** run for 14 Oct 2020, it reproduces the Level 4 numbers exactly (882.2 / 1,131.3 / 1,218.3 km²).

**Radar availability in 2026:** track 164 now passes **every 6 days** (Sentinel-1A, 1C and 1D), and the archive runs 1–3 days behind.

**It measures; it does not predict.** It shows where water is *now*. It cannot say whether a flood will happen.

### First real use: 26 September 2026

| Flooded cropland | 26 Sep 2026 | 2025 | 2024 | 2023 |
| --- | --- | --- | --- | --- |
| VH threshold | 1,326 km² | 627 | 220 | 143 |
| U-Net VV only | 1,623 km² | 668 | 257 | 152 |
| **U-Net VV+VH (selected)** | **1,998 km²** | 722 | 529 | 312 |

**Verdict: UNUSUAL FLOODING**, 3.8–6.3× the usual amount, and all 3 methods agree. It is bigger than the 2020 disaster.

| Worst districts | Flooded cropland | Share of the district's cropland |
| --- | --- | --- |
| Preah Netr Preah | 576 km² | 62 % |
| Mongkol Borei | 369 km² | 53 % |
| Phnum Srok | 346 km² | 55 % |
| Ou Chrov | 230 km² | 47 % |
| Serei Saophoan | 134 km² | 62 % |

![Flood check 26 Sep 2026](../results/check/2026-09-26/map.png)

**Checks on this result:**
- **News confirms it.** Heavy rain from 24 Sep 2026 flooded 10 provinces, and Banteay Meanchey was among the worst hit, with over 1,300 families evacuated ([Khmer Times](https://www.khmertimeskh.com/502032326/thousands-displaced-as-severe-floods-hit-10-provinces), [AKP](https://www.akp.gov.kh/post/detail/382367)).
- **The new satellite is not creating fake water.** The 26 Sep image comes from Sentinel-1D, which the model was never tested on. On stable ground (towns, roads) its brightness is within the normal range and slightly brighter. A brighter image would *hide* water, not invent it.
- **The official figure is smaller.** About 50,000 ha (500 km²) of rice was reported affected across all 10 provinces as of 28 Sep. As in 2020, the satellite measures *all water on fields*, while officials count *damaged rice*.

Result files: [results/check/2026-09-26/](../results/check/2026-09-26/report.md).

---

## 9. Limits: what this project does not show

1. **Water hidden under the rice canopy is not proven on Cambodian ground.** Level 3 shows it on the benchmark (mostly other countries). The Cambodian hand labels only contain water visible in photos, and free data cannot close this gap here (§6).
2. **The benchmark's Cambodian test scene is young rice** (August), not tall rice.
3. **The selected model over-detects** outside cropland. Do not use its forest and grassland numbers.
4. **Mapped flood area is larger than official figures** (2020: 3.9× the reported figure). The two probably measure different things; this is not resolved.
5. **Small evidence base:** one labeller (no agreement score), 17 squares of 4 km², one training run per model.
6. **Sentinel-1C and 1D were never tested against labels.** The brightness check passed, but accuracy on them is assumed, not measured.
7. **WorldCover "cropland" is not the same as "rice".** It includes other crops.

---

## 10. Reviews and corrections

The work was audited by a second AI (Gemini) several times. Each finding was checked on its merits: real bugs were fixed, and wrong findings were answered in writing.

| When | Found | Result |
| --- | --- | --- |
| 21 Sep | 9 issues, incl. broken elevation mosaic, no-data turned into "water", labels losing land type on dry pixels | All fixed (`1ed092c`, `9f55322`) |
| 22 Sep | Plan text and code defined "bright" differently | Measured both ways; the verdict holds under both |
| 29 Sep | 17 points on the summary, hidden-water check and report | 13 accepted and fixed (`660d00f`). The biggest: the report quoted accuracy from the wrong map layer (80 % → **74 %**). 2 were partly wrong, 1 was rejected, 1 found nothing |

---

## 11. Every output, and where it is

### Documents (`docs/`)

| File | What it is |
| --- | --- |
| [PROJECT_REPORT.md](PROJECT_REPORT.md) | This file |
| [SUMMARY.md](SUMMARY.md) | 5-minute summary |
| [level7_report.md](level7_report.md) | Flood report for decision-makers (generated) |
| [level0_inventory.md](level0_inventory.md) | Dataset inventory |
| [level1_baseline.md](level1_baseline.md) | Threshold baseline, the bright-rice finding |
| [level2_failure_analysis.md](level2_failure_analysis.md) | Why thresholding fails |
| [level3_results_v11.md](level3_results_v11.md) | Hypothesis test (live result) |
| [level3_results.md](level3_results.md) | Hypothesis test v1.0 (record) |
| [level4_pipeline_switch.md](level4_pipeline_switch.md) | Why the first model could not be used on Cambodia |
| [level4_cambodia.md](level4_cambodia.md) | 2020 flood maps and the normal-year comparison |
| [level4_tierb_scores.md](level4_tierb_scores.md) | Scores on hand labels, and the hidden-water check |
| [progress_explained_simple.md](progress_explained_simple.md), [radar_physics_explained_simple.md](radar_physics_explained_simple.md), [radar_preprocessing_explained_simple.md](radar_preprocessing_explained_simple.md) | Plain-language explainers |

### Results (`results/`, the source of every number)

| Path | Contents |
| --- | --- |
| `experiment_log.csv` | Every run and every selection, in order |
| `level1/`, `level2/` | Baseline scores, failure analysis |
| `level3_rtc/<model>/` | Per-model metrics (valid, test), per-tile scores, configs |
| `level4/change_detection.json`, `normal_years.json` | 2020 flood areas, normal-year comparison |
| `level4/tierb_scores.json` | Scores on the hand labels |
| `level4/hidden_water_feasibility.json` | Hidden-water check |
| `level7/districts.csv`, `report.json` | Per-district areas, report numbers |
| `check/2026-09-26/` | The September 2026 flood check |

### Figures (`docs/figures/`)

`level0_mekong_chip` · `level1_scores`, `level1_brightness` · `level2_taxonomy`, `level2_joint`, `level2_examples` · `level3_rtc_valid`, `level3_rtc_test`, `level3_rtc_per_chip` · `level4_flood_map`, `level4_timeseries`, `level4_normal_years` · `level7_districts` · `tier_b_tiles_1–4` · `what_water_looks_like`, `training_sample_illustrated`

### Data and labels

| Path | Contents |
| --- | --- |
| `data/aoi/` | Province and district boundaries |
| `data/labels/tierB_bmc_oct2020.gpkg` | The hand labels (95 confirmed water polygons) |
| `data/labels/LABELLING_PROTOCOL.md` | Labelling rules (frozen v1.2) |
| `data/labels/review.html` | The browser review page |
| `evaluation_plan.md` | Pre-registered pass criteria (frozen v1.1) |

---

## 12. How to run it

**Check a date on Colab (easiest):**
1. Open https://colab.research.google.com → File → Open notebook → GitHub → `SoSereysokbotra/mekong-flood-analysis` → `notebooks/colab_check_flood.ipynb`
2. Runtime → Change runtime type → **T4 GPU**
3. In the second cell, type the date (e.g. `2026-10-02`) or leave it empty for the newest image
4. Runtime → **Run all**. After 10–20 minutes the map and report appear. They are saved to `MyDrive/mfi/check/<date>/`

It needs `MyDrive/mfi/level3_rtc_checkpoints.zip` on Google Drive (already there).

**On the laptop:** `.venv\Scripts\python scripts/check_flood.py --date 2026-09-26`. Each radar image is ~240 MB, so it is slow on a home connection.

**Rebuild the reports:** `scripts/level7_district_areas.py`, then `scripts/level7_report.py`.

**Set up from scratch:** see [README.md](../README.md).

---

## 13. What could come next

| Idea | Value | Cost |
| --- | --- | --- |
| A second person labels 5 squares | Gives a labeller-agreement score (currently missing) | ~1 hour of someone's time |
| Keep checking the 2026 flood every 6 days | Shows rising or falling water, district by district | 20 min on Colab per image |
| Test on Sentinel-1C/1D against labels | Turns limit 6 from "assumed" into "measured" | New hand labels on a 2026 date |
| L-band radar (ALOS-2) or field reports | The only way to test hidden water under rice | Data not free |
| Full automation (runs every pass by itself) | A real monitoring service | A separate software project |
| Other provinces | Wider coverage | Mostly re-running with a different boundary |

---

## 14. Glossary

| Term | Meaning |
| --- | --- |
| **Sentinel-1** | European radar satellites. Free data, sees through clouds and at night |
| **VV, VH** | The two radar "bands" (polarisations). VH is more sensitive to vegetation |
| **dB (decibel)** | Radar brightness scale. More negative means darker (e.g. −29 dB = water) |
| **RTC** | Radiometrically terrain-corrected: radar pre-processed so hills do not distort brightness |
| **Double bounce** | Radar pulse bouncing water → stem → satellite, making flooded rice bright |
| **Threshold** | Rule "darker than X = water". The standard simple method |
| **U-Net** | A type of AI model that labels every pixel of an image and can use the surrounding area |
| **Recall** | Of all real flood water, how much the model found |
| **Precision** | Of everything the model called flood, how much really was flood |
| **IoU** | Overlap between predicted and real water (1.0 = perfect) |
| **AUC** | How well one number separates two groups (0.5 = coin toss, 1.0 = perfect) |
| **Held out** | Kept completely away from training, so the test is fair |
| **Pre-registered / frozen** | Rules written and committed *before* seeing results, so they can't be bent afterwards |
| **Tier B labels** | Hand labels drawn for this project in Cambodia |
| **Track 164** | The satellite's orbit path that covers Banteay Meanchey (passes ~06:00 local time) |
| **Sen1Floods11** | Public dataset of 446 hand-labelled flood images from 11 countries |
| **WorldCover** | ESA map of land types (cropland, trees, built-up…), used to split scores |
