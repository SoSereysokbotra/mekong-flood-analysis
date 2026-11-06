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

Labelled water: 4.08 km² (10,194 px at 20 m), of which 8,868 px on cropland. Labelled dry: 133,348 px.
18 of 20 tiles carry a decision.

The flood check itself says **NORMAL FOR THE SEASON** for 2 Oct: 1,234 km² flooded cropland
(selected model) vs a median of 938 km² on the same dates of 2023-2025 (1.3×; 2025 was also wet).
The 26 Sep check had said UNUSUAL. This is a statement about the comparison years, not about accuracy.

## 2. Scores: total water on the flood date (the headline)

| Method | cropland IoU | cropland recall | cropland precision |
| --- | --- | --- | --- |
| VH threshold (`otsu_vh_global`) | 0.496 | 0.853 | 0.542 |
| U-Net VV only (`unet_vv_ce`) | 0.527 | 0.972 | 0.535 |
| **U-Net VV+VH, selected (`unet_vvvh_cropw`)** | **0.529** | **0.975** | **0.536** |

Same comparison in 2020 (Sentinel-1A, 14 Oct 2020):

| Method | cropland IoU | cropland recall | cropland precision |
| --- | --- | --- | --- |
| VH threshold | 0.498 | 0.553 | 0.835 |
| U-Net VV+VH, selected | 0.713 | 0.801 | 0.867 |

## 3. What this says

1. **The ranking holds, but the margin is small.** The selected model is still best on cropland
   (IoU 0.529 vs 0.496), and finds almost all labelled water (recall 0.975 vs 0.853).
   The 2020 margin (0.713 vs 0.498) is **not** reproduced.
2. **Precision fell for every method, the threshold included** (cropland 0.54 vs 0.84-0.87 in 2020).
   Because the plain "dark = water" threshold drops just as much as the U-Nets, the drop is not
   caused by the model. All three methods see water where the optical labels say dry.
   Possible causes, which this data **cannot separate**:
   - the labels miss water: only NDWI candidates were reviewed, and the 16 "unsure" areas are excluded;
     shallow water mixed with plants may not pass the NDWI threshold;
   - water changed in the 2 days between radar (2 Oct) and optical (4 Oct);
   - wet soil or smooth fields that look dark on radar;
   - a Sentinel-1C/1D calibration difference;
   - water under the rice canopy (radar sees it, optical cannot). This applies to the U-Nets but
     not to the threshold, which only finds dark water, so it cannot be the whole story.
3. **Sentinel-1C/1D:** recall is high and the ranking holds, so the newer satellites do not break the
   method. Precision is low for an unexplained reason, so S1C/1D area figures should be read as an
   **upper bound** until this is understood.

## 4. The "new flood" comparison is not meaningful this time

No confirmed 2026 polygon was labelled as permanent water (29 cropland/vegetation flood, 5 other flood,
0 open water), so the "new flood" labels are identical to the "total water" labels. They include water
that was already there on the "before" date (14 Sep), which the flood map does not count as new by design.
The selected model's lower new-flood score (cropland IoU 0.347) therefore mostly measures water it saw
already on 14 Sep, not missed flood. These numbers are in the JSON for completeness and should not be quoted.

## 5. Limits (as in 2020)

- One labeller, candidates pre-drawn from NDWI (anchoring risk, protocol §5b). 16 of 66 rejected, so the
  review was not a rubber stamp.
- Optical cannot see under the canopy: flooded-vegetation recall is not a fair test (vegetation n = 793 px,
  too small anyway).
- 4 km² of labels on 18 tiles in one province; one event.
