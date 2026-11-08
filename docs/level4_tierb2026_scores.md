# Tier B 2026: the flood check scored on the September 2026 flood

Written 6 Nov 2026. Rules fixed in advance: `data/labels/LABELLING_PROTOCOL.md` §9 (v1.3, 1 Oct 2026).
Numbers: `results/check/2026-10-02/tierb_scores.json` (2026) and `results/level4/tierb_scores.json` (2020).
If this page disagrees with those files, the files win.

**What is new here:** the first accuracy measurement on **Sentinel-1C/1D** (the 2 Oct 2026 pass),
which the models were never trained or tested on.

## 1. What was done

| Step | Result | Record |
| --- | --- | --- |
| Scene selection (rule §9.1, deadline 31 Oct) | optical **4 Oct 2026** (17 of 20 tiles ≥ 50 % clear), radar **2 Oct 2026** (2 days apart) | `data/labels/2026/selected.json`, commit `1fcee72`, made before any 2026 scene was viewed |
| Candidates (§5b, NDWI on 4 Oct) | 66 water candidates, 34 cloud areas | commit `cb0ea6c` |
| Review (Sobotra, 6 Nov 2026) | **34 water, 16 not water, 16 unsure**, all 66 reviewed | `data/labels/2026/review_summary.json` |
| Map scored (§9.2) | flood check for 2 Oct 2026, default settings, "before" pass 14 Sep 2026 | `results/check/2026-10-02/report.md` |

**Tiles.** All 20 tiles had an event scene and are scored. **12 tiles** carry a labeller decision (they had
at least one candidate). **8 tiles** had no water candidate: on 6 of them (BMC_CROP_03, 04, 08, 09, 11,
BMC_VEGE_17) only cloud areas were outlined, and 2 (BMC_CROP_13, 19) were clear with nothing outlined.
On those 8, every clear pixel counts as dry, as the protocol states ("every other pixel in a reviewed tile is
DRY"). Labelled water: 4.08 km² (8,868 px on cropland).

The flood check itself says **NORMAL FOR THE SEASON** for 2 Oct: 1,234 km² flooded cropland
(selected model) vs a median of 938 km² on the same dates of 2023-2025 (1.3×; 2025 was also wet).
The 26 Sep check had said UNUSUAL. This is a statement about the comparison years, not about accuracy.

## 2. Scores: total water on the flood date (the headline)

| Method | cropland IoU | cropland recall | cropland precision |
| --- | --- | --- | --- |
| VH threshold (`otsu_vh_global`) | 0.493 | 0.853 | 0.539 |
| U-Net VV only (`unet_vv_ce`) | 0.527 | 0.972 | 0.535 |
| **U-Net VV+VH, selected (`unet_vvvh_cropw`)** | **0.529** | **0.975** | **0.536** |

Same comparison in 2020 (Sentinel-1A, 14 Oct 2020):

| Method | cropland IoU | cropland recall | cropland precision |
| --- | --- | --- | --- |
| VH threshold | 0.498 | 0.553 | 0.835 |
| U-Net VV+VH, selected | 0.713 | 0.801 | 0.867 |

### Sensitivity runs (not the headline)

| Run | Tiles | selected: IoU / recall / precision (cropland) | threshold: IoU / recall / precision |
| --- | --- | --- | --- |
| Headline (above) | 20 | 0.529 / 0.975 / 0.536 | 0.493 / 0.853 / 0.539 |
| "Unsure" counted as water (protocol §5) | 20 | 0.529 / 0.971 / 0.537 | 0.495 / 0.853 / 0.541 |
| Only the 12 tiles with a decision | 12 | 0.530 / 0.975 / 0.537 | 0.505 / 0.853 / 0.553 |
| Also ignore SCL 1, 2 (defective, dark area) | 20 | 0.529 / 0.975 / 0.536 | 0.493 / 0.853 / 0.539 |
| Also ignore SCL 1, 2, 7 (+ unclassified) | 20 | 0.537 / 0.975 / 0.545 | 0.513 / 0.879 / 0.552 |

The cropland result does not depend on these choices. The 2026 scene has no SCL 2 pixels and 4 % SCL 7, so poorly classified optical pixels do not explain the low 2026 precision (in 2020 the same check raises every score; `docs/level4_tierb_scores.md` §6). (The unsure areas add 3.95 km² of water, but
almost all of it is off cropland.)

### Correction made after review

The first scoring run (commit `1a9f64c`) picked the tiles to score as "tiles that have any polygon".
That dropped BMC_CROP_13 and BMC_CROP_19 (clear, no candidate) and would have dropped any tile whose
candidates were all rejected. Found in the Gemini review; fixed in `scripts/tierb2026.py` (`scored_tiles()`):
the tile set is now every tile whose event scene has data (`tiles_to_score()`, shared with the 2020 scorer, which gives the same 17 tiles and identical 2020 scores; see `docs/level4_tierb_scores.md` §6). Effect: threshold cropland IoU 0.496 → 0.493,
selected model unchanged (0.529). The old rows stay in `results/experiment_log.csv` (`tierb2026_*`);
the corrected ones are `tierb2026fix_*`.

## 3. What this says

1. **The ranking holds, but the margin is small.** The selected model is still best on cropland
   (IoU 0.529 vs 0.493), and finds almost all labelled water (recall 0.975 vs 0.853).
   The 2020 margin (0.713 vs 0.498) is **not** reproduced.
2. **Precision fell for every method, the threshold included** (cropland ~0.54 vs 0.84-0.87 in 2020).
   The plain "dark = water" threshold drops as much as the U-Nets, so the drop is not caused by the model.
   All three methods see water where the labels say dry. Possible causes, which this data **cannot separate**:
   - **How "dry" is defined.** Only NDWI candidates were shown to the labeller. Every other clear pixel in a
     tile counts as dry without a human looking at it. Water that NDWI misses (shallow water with plants
     sticking out, muddy water, patches under 0.12 ha removed by the candidate filter) therefore becomes a
     false positive for any radar method that sees it, dark-water threshold included. This is the most direct
     explanation, but it is not sufficient on its own: 2020 used the same design and reached precision 0.85,
     so it explains the drop only if 2026 had much more water that NDWI misses.
   - Water changed in the 2 days between radar (2 Oct) and optical (4 Oct).
   - Wet soil or smooth fields that look dark on radar.
   - A Sentinel-1C/1D calibration difference.
3. **Sentinel-1C/1D:** recall is high and the ranking holds, so the newer satellites do not break the
   method. Precision is low for a reason not yet separated, so S1C/1D area figures should be read as an
   **upper bound** until this is understood.

## 4. The "new flood" comparison is not meaningful this time

No confirmed 2026 polygon was labelled as permanent water (29 cropland/vegetation flood, 5 other flood,
0 open water), so the "new flood" labels are identical to the "total water" labels. They include water
that was already there on the "before" date (14 Sep), which the flood map does not count as new by design.
The selected model's lower new-flood score (cropland IoU 0.347) therefore mostly measures water it saw
already on 14 Sep, not missed flood. These numbers are in the JSON for completeness and should not be quoted.
The review page had no "water, but already there before" button, so this could not have been labelled;
add one if this procedure is used again.

## 5. Limits (as in 2020)

- One labeller, candidates pre-drawn from NDWI (anchoring risk, protocol §5b). 16 of 66 rejected, so the
  review was not a rubber stamp.
- Optical cannot see under the canopy: flooded-vegetation recall is not a fair test (vegetation n = 793 px,
  too small anyway).
- 4 km² of labels on 12 decided tiles in one province; one event.
