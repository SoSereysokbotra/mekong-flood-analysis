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

## 5. Can the hidden-water gap be closed with free data? Measured: no

**Date:** 29 September 2026 · **Script:** `scripts/level4_hidden_water_feasibility.py` → `results/level4/hidden_water_feasibility.json`. No radar or model output is read.

Before asking the labeller to add polygons for water under the canopy (§4, item 1), I checked whether any free evidence other than C-band radar could support them. There were two candidate routes, and neither works here.

**Terrain.** The idea: low ground next to confirmed water is probably flooded. But the cropland tiles are almost perfectly flat. Across a 2 km tile the median elevation spread (5th to 95th percentile) is **1.52 m**, which is about the vertical noise of the Copernicus DEM. Of the green land within 300 m of confirmed water, 75–100 % sits within 0.5 m of that water in every cropland and water tile. The DEM therefore cannot separate a flooded field from a dry one next to it. A terrain rule would label *everything* near water as flooded, which is an assumption, not evidence. Also, 9 of the 12 cropland tiles have no confirmed water at all, so there is nothing to measure height against.

**Post-event optical.** The idea: a field that is green on the flood date but open water in November was probably flooded under its canopy all along. Measured on the 18 tiles that have both an event-date and a post-event scene, masking cloud separately on each date: only **1.16 km²** fits that pattern, and **none** of it is on cropland. Almost all of it (1.04 km²) is in one vegetation tile, `BMC_VEGE_12`, where water *grew* between the dates (39 % → 63 % of the tile). That means water may have arrived after 14 October, so it cannot be read back as hidden water on the flood date.

**This test is weak, and a zero from it is not evidence of no hidden water.** Floods recede. Water hidden under rice in October would usually drain, or stay hidden under a lodged or rotting crop, rather than show up as open water in November. (Point raised in an external review, 29 Sep 2026; accepted.) The test was a search for *usable label evidence*, and on that question the answer stands: this route yields almost none.

**Conclusion.** In this province, the only sensor that sees water under a rice canopy is radar, and radar is the thing being tested. Closing the gap needs independent evidence of a kind this project does not have:
- L-band radar (ALOS-2), which penetrates the canopy. Not freely available for this date.
- Field reports or photographs located to the field.
- Very-high-resolution imagery on the event date.

The gap in §3 item 1 is therefore recorded as **not closable with free data at this site**, not merely as "not yet done".
