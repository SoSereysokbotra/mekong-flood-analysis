# Level 4 — Scored against Cambodian hand labels (Tier B)

**Date:** 29 September 2026
**Labeller:** Sobotra, 116 candidates reviewed in one session via `data/labels/review.html`
**Labels:** `data/labels/tierB_bmc_oct2020.gpkg`, layer `flood` — 95 confirmed water polygons, 21 rejected, 104 cloud/uncertain areas excluded
**Scripts:** `scripts/make_label_candidates.py` → `make_review_page.py` → `apply_review.py` → `level4_score_tierb.py`
**Artefacts:** `results/level4/tierb_scores.{csv,json}`, `data/labels/review_summary.json`

This is the Cambodia-specific test the plan called for: the three Level 4 methods judged against labels a human confirmed, on the flood date, at rice-ripening stage.

## 1. Scores

17 of 20 tiles reviewed (three had no usable event-date optical). Scored inside those tiles only; cloud and unsure areas excluded.

### Total water — the map of all water on 14 Oct, against labels of classes 1, 2 and 3

| Method | all IoU | all recall | all prec | **cropland IoU** | **cropland recall** | **cropland prec** |
| --- | --- | --- | --- | --- | --- | --- |
| VH threshold (Level 1) | 0.424 | 0.695 | 0.521 | 0.498 | 0.553 | 0.835 |
| U-Net VV only | 0.488 | 0.772 | 0.571 | 0.612 | 0.669 | 0.879 |
| **U-Net VV+VH cropland-weighted (selected)** | 0.478 | **0.844** | 0.525 | **0.713** | **0.801** | 0.867 |

### New flood — water at peak minus pre-event water, against classes 1 and 2 (permanent water excluded)

| Method | all IoU | all recall | all prec | cropland IoU | cropland recall | cropland prec |
| --- | --- | --- | --- | --- | --- | --- |
| VH threshold | 0.232 | 0.470 | 0.314 | 0.483 | 0.533 | 0.839 |
| U-Net VV only | 0.322 | 0.624 | 0.400 | 0.613 | 0.668 | 0.881 |
| **U-Net VV+VH cropw (selected)** | 0.304 | 0.657 | 0.362 | **0.677** | **0.735** | **0.894** |

Scorable area: 5.82 km² of water for the total comparison, 3.53 km² for new flood, against ~41 km² of dry.

## 2. What this says

**On Cambodian cropland the selected model beats the Level 1 threshold by a wide margin**: cropland IoU 0.713 vs 0.498 and recall 0.801 vs 0.553 on total water, at the same precision (0.867 vs 0.835). The same ordering holds on new flood (0.677 vs 0.483). The model chosen on a benchmark, under criteria frozen before training, transfers to a different country, a different season and a different crop stage — and the ordering of the three methods is the same here as it was on the benchmark.

**The selected model's weakness also transfers.** Its *overall* precision is the lowest of the three (0.525 vs 0.571), because it over-detects on the vegetation stratum. That was measured at Level 3 (4× the cropland false positives of the VV-only model) and predicted for Level 4; it is now confirmed on real ground. For a general flood map the VV-only U-Net is still the better choice; for cropland specifically the selected model is clearly better.

**Against the reported figure.** These labels cover 17 tiles of 4 km², not the province, so they cannot settle the Tier E discrepancy directly. What they do settle is which method to trust on cropland, and that method is the one giving the *largest* provincial extent — which pushes against, not toward, the reported 282 km².

## 3. What these labels cannot test — read before citing any number here

1. **The labels cannot contain water that optical could not see.** They were seeded from an NDWI water index on Sentinel-2 and then human-filtered. Flooded rice under a closed canopy is invisible to optical and therefore absent from the labels. **Recall on flooded vegetation is not a fair test here** — the very case this project exists to study is the case the labels are blind to. The flooded-vegetation recall numbers in `tierb_scores.json` should not be quoted as evidence for or against the hypothesis.
2. **Anchoring.** Candidates were pre-drawn (protocol v1.2 §5b). The labeller rejected 21 of 116 (18 %), which shows genuine judgement rather than acceptance, but the labels are still closer to an NDWI threshold than fully independent ones would be. No polygons were *added* for water the candidates missed, so the mitigation in v1.2 §5b(3) was not exercised.
3. **One labeller, no agreement measure.** Protocol §1 allows this and requires it be said: Cohen's κ is not reported because there was no second labeller. It was not substituted with a second pass by the same person.
4. **Small and uneven.** 5.8 km² of labelled water across 17 tiles; the open-water and built strata have too few pixels to support per-stratum conclusions (220 built water pixels). Only the cropland numbers are on a sample worth quoting.
5. **Optical is 1–6 days off the radar date** (S2 on 15 or 20 Oct against S1 on 14 Oct). Water moves in that window.

## 4. Where this leaves Level 4

The plan's bar for Level 4 was "a flood map of a real Cambodian disaster, scored against Cambodia-specific labels, with results split by land type". That is now met, with the limitations above stated.

What would strengthen it, in order of value:
1. **Labels that are not optically seeded** — a labeller adding polygons where they believe water exists under canopy, using terrain and hydrology, would let the flooded-vegetation recall be tested honestly. This is the single missing piece for the project's core claim on Cambodian ground.
2. A second labeller on 5 tiles, for κ.
3. The three unlabelled tiles, if a clearer optical scene can be found.
