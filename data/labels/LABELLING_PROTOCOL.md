# Tier B labelling protocol — Banteay Meanchey, October 2020

**Status: FROZEN v1.0, 23 September 2026.** Frozen before any polygon was drawn (Mistake_avoidance #7). Changes after this point require a new version with a dated changelog entry and a written reason, and any tile already labelled under the old version is re-checked.
**Purpose:** hand-labelled flood extent for the anchor event, specifically capturing **flooded rice fields**, including the bright double-bounce case that radar thresholding misses. These labels are the Cambodia-specific test set (plan Section 5, Tier B). They are never used for training.

## 1. Who, when, with what

| Field | Value |
| --- | --- |
| Labeller 1 | Sobotra (project owner). Record start date, end date and hours in `data/labels/labelling_log.csv` |
| Labeller 2 (agreement subset, ≥ 5 tiles) | To be named. If no second labeller is available, that is recorded as a limitation and Cohen's κ is not reported — it is not substituted with a second pass by Labeller 1 |
| Software | QGIS ≥ 3.34 |
| Output format | GeoPackage `data/labels/tierB_bmc_oct2020.gpkg`, layer `flood`, EPSG:32648 |
| Attributes per polygon | `class` (int, see §3), `confidence` (1–3), `evidence` (text, see §4), `labeller`, `date_labelled`, `tile_id` |

## 2. What is being labelled

Surface water present on **14 October 2020** (the Sentinel-1 track-164 pass, ~06:00 local) that was **not** present on 26 September 2020 (the pre-event pass). Permanent water is labelled separately so it can be excluded (Tier D), not ignored.

Every pixel inside a labelling tile receives exactly one class. Tiles are 2 × 2 km squares in EPSG:32648, fixed by `scripts/level4_select_tiles.py` before this protocol was frozen and listed in `data/labels/tiles.geojson`: 20 tiles, 80 km², selected from 1,417 candidates by land-type fraction with an 8 km minimum separation, order shuffled with seed 0. **No model output was used in the selection.**

| # | Tile id | Stratum | Centre lat, lon | Land cover |
| --- | --- | --- | --- | --- |
| 1 | `BMC_CROP_01` | cropland | 13.6995, 103.0815 | cropland 100% |
| 2 | `BMC_WATE_02` | water | 13.5559, 103.2120 | cropland 81%, vegetation 12% |
| 3 | `BMC_CROP_03` | cropland | 13.6801, 102.9153 | cropland 100% |
| 4 | `BMC_CROP_04` | cropland | 13.7724, 103.1549 | cropland 100% |
| 5 | `BMC_VEGE_05` | vegetation | 13.3943, 103.3794 | vegetation 100% |
| 6 | `BMC_BUIL_06` | built | 13.6410, 102.5830 | built 43%, cropland 12%, other 17%, vegetation 26% |
| 7 | `BMC_CROP_07` | cropland | 13.7351, 103.0073 | cropland 100% |
| 8 | `BMC_CROP_08` | cropland | 13.8074, 103.0066 | cropland 100% |
| 9 | `BMC_CROP_09` | cropland | 13.8981, 103.0429 | cropland 100% |
| 10 | `BMC_CROP_10` | cropland | 13.6628, 103.0079 | cropland 100% |
| 11 | `BMC_CROP_11` | cropland | 13.9185, 103.3573 | cropland 100% |
| 12 | `BMC_VEGE_12` | vegetation | 13.8458, 103.3023 | vegetation 100% |
| 13 | `BMC_CROP_13` | cropland | 13.6602, 102.7122 | cropland 100% |
| 14 | `BMC_CROP_14` | cropland | 13.7012, 103.3034 | cropland 100% |
| 15 | `BMC_WATE_15` | water | 13.7915, 103.3027 | cropland 13%, open_water 80% |
| 16 | `BMC_BUIL_16` | built | 13.5364, 103.0274 | built 37%, cropland 20%, vegetation 41% |
| 17 | `BMC_VEGE_17` | vegetation | 13.9359, 103.2646 | vegetation 96% |
| 18 | `BMC_CROP_18` | cropland | 13.4436, 102.7327 | cropland 100% |
| 19 | `BMC_CROP_19` | cropland | 13.8817, 103.2651 | cropland 100% |
| 20 | `BMC_BUIL_20` | built | 13.5902, 102.9715 | built 66%, vegetation 30% |

Label them in the order above. Do not skip ahead to the interesting-looking ones: the order is fixed so that fatigue and learning effects are spread across strata rather than concentrated in one.

## 3. Classes

| Code | Class | Definition |
| --- | --- | --- |
| 1 | `flood_open` | New water with no emergent vegetation visible |
| 2 | `flood_vegetated` | New water with emergent vegetation (rice, grass, shrubs) — **this is the target class** |
| 3 | `permanent_water` | Water present in both the pre-event and event dates, or JRC occurrence ≥ 90 % |
| 0 | `dry` | No surface water |
| −1 | `uncertain` | Evidence conflicts or is missing; **use freely — never guess** |

Rule of thumb for 1 vs 2: if the land cover on the pre-event optical image is cropland or vegetation and the area is flooded on the event date, it is `flood_vegetated` unless the vegetation is clearly gone (bare water surface).

## 4. Evidence hierarchy — what you may look at, in order

The point of Tier B is to label the case radar gets wrong. **If you label by tracing dark radar pixels, the labels inherit the exact bias this project studies and the test is worthless.** Therefore:

1. **Primary:** cloud-free optical imagery closest to 14 Oct 2020. Sentinel-2 L2A 30 Oct 2020 tile T48PUV (27 % cloud) is the nearest; also Planet / Google Earth historical imagery if available. Look at water colour, standing water between crop rows, submerged field bunds.
2. **Primary:** pre-event optical (Sep 2020 or Dec 2019 dry season) to establish land cover and permanent water.
3. **Supporting:** elevation (Copernicus DEM) and hydrology — low-lying land adjacent to flooded rivers / Tonle Sap arms is more plausibly flooded.
4. **Supporting:** the OCHA 4W report and news for village-level confirmation.
5. **Last, and only to refine boundaries:** Sentinel-1 VV/VH on the event date. Use it to snap a boundary that optical has already established. **Never** use radar darkness alone to decide whether an area is flooded, and **never** mark an area dry because the radar is bright.

Record in `evidence` which sources were decisive, e.g. `S2 2020-10-30; DEM`.

## 5. Confidence

| Value | Meaning |
| --- | --- |
| 3 | Two independent sources agree (e.g. optical + hydrology) |
| 2 | One clear source |
| 1 | Plausible but weak — consider `uncertain` instead |

Polygons with confidence 1 are scored in a sensitivity run but excluded from the primary score.

## 6. Procedure

1. Read this protocol in full. Open QGIS project `data/labels/tierB.qgz` (layers pre-loaded and styled; radar layer *off* by default).
2. For each tile in `tiles.geojson`, in the listed order:
   a. With radar off: establish land cover and permanent water from pre-event optical.
   b. With radar off: draw `flood_open` / `flood_vegetated` from event-date optical + DEM.
   c. Mark anything you cannot decide as `uncertain`.
   d. Only now turn radar on, and only to refine boundaries of polygons already drawn.
   e. Fill attributes. Save. Log time spent.
3. Labeller 2 repeats step 2 independently on the agreement subset **without seeing Labeller 1's polygons**.
4. Agreement is computed by `scripts/level4_label_agreement.py` (per-class pixel agreement and Cohen's κ) and reported with the Level 4 results. Disagreements are *not* reconciled by discussion before scoring; the primary score uses Labeller 1, and κ is reported alongside.

## 7. Crop-stage note for October

Wet-season rice in north-west Cambodia is transplanted June–August and harvested November–December. On 14 October, rice is in the reproductive / ripening stage, typically 80–120 cm tall and dense. Flooded fields at this stage are exactly where double bounce is expected, and where the radar will look *bright*, not dark. Expect to find `flood_vegetated` areas that look like dry land on radar. That is the point.

## 8. What is frozen by committing this file

The classes, the evidence hierarchy, the tile list and labelling order, and the rule that the primary score uses Labeller 1 with confidence ≥ 2. Changes after labelling starts are recorded as a new protocol version with a dated changelog below, and any tiles labelled under the old version are re-checked.

## Changelog

- v0.1 — 22 Sep 2026 — draft.
- **v1.0 — 23 Sep 2026 — frozen.** Added the fixed tile list and labelling order (the grid was generated in the meantime), named Labeller 1, and made explicit that κ is omitted rather than faked if no second labeller is found. Classes, evidence hierarchy, confidence scale and procedure are unchanged from v0.1.
