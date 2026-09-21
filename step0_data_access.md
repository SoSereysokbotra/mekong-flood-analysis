# Step 0 — Data access note

**Date:** 21 September 2026
**Study area:** Banteay Meanchey province, Cambodia (adm1 pcode KH01, 6,146 km²)
**AOI bbox (lon/lat):** 102.335, 13.359, 103.442, 14.250 — polygon in `data/aoi/banteay_meanchey_adm1.geojson` (OCHA COD-AB, HDX)

All checks were made programmatically against live APIs on the date above.

## Summary

| Check | Result | Notes |
| --- | --- | --- |
| Sentinel-1 RTC (ARD) over AOI, Sep–Nov 2020 | **Obtained** | Microsoft Planetary Computer `sentinel-1-rtc`: 97 scenes, VV+VH, gamma-nought, 10 m, EPSG:32648 |
| Sentinel-1 GRD (raw) over AOI | Available | 93 scenes on Planetary Computer; also on Copernicus Data Space. Not needed if RTC works |
| Sen1Floods11 benchmark | **Obtained** | Public GCS bucket `gs://sen1floods11/v1.1`. Hand-labelled subset downloaded (446 chips). Contains a **Cambodia event** |
| ESA WorldCover 10 m | **Obtained** | Planetary Computer: 2020 v1.0 and 2021 v2.0 tiles cover AOI |
| JRC Global Surface Water | **Obtained** | Planetary Computer `jrc-gsw` tile `100E_20N`, 1984–2020 edition; occurrence / seasonality / recurrence layers |
| DEM | **Obtained** | Copernicus DEM GLO-30 (4 tiles) and NASADEM on Planetary Computer |
| Sentinel-2 cloud-free scene near event (Tier C) | **Marginal** | Best in Oct 2020: 27 % cloud on 30 Oct (tile T48PUV), after the peak. Nothing usable 1–21 Oct. Tier C is optional by design |
| Sentinel Asia flood polygons (Tier F) | **Not obtained** | Not on HDX. Web GIS is member-only. Not pursued further — plan does not depend on it |
| UNOSAT Cambodia 2020 vectors (Tier F) | **Not obtained** | HDX search: only a 2018 Long An (Vietnam) product. No Cambodia 2020 |
| Province-level figures (Tier E) | **Obtained** | OCHA "Cambodia 4W Flood Response" round 2 (Dec 2020, XLSX) downloaded to `data/raw/hdx/` |
| Admin boundaries | **Obtained** | OCHA COD-AB Cambodia adm0–3, GeoJSON, `data/raw/hdx/` |
| Kuro Siwo, UrbanSARFloods | Deferred | Not checked. Sen1Floods11 is sufficient for Levels 0–3; add only if flooded-cropland examples turn out too few |

**Decision:** Tier F is not available → proceed with A + B + D (+ E), as the plan specifies. No change to the plan.

## Sentinel-1 acquisition calendar over the AOI

Relative orbit **26, ascending** passes every 6 days (alternating S1A / S1B). This is the same track as the Sen1Floods11 Cambodia event (rel. orbit 26, ascending, 5 Aug 2018), so benchmark chips and the Oct 2020 scenes share viewing geometry.

| Date | Satellite | Role (flood 1–21 Oct, peak ~14 Oct) |
| --- | --- | --- |
| 2020-09-17 | S1A | pre |
| 2020-09-23 | S1B | pre |
| 2020-09-29 | S1A | **pre (reference)** |
| 2020-10-05 | S1B | early flood |
| 2020-10-11 | S1A | **during** |
| 2020-10-17 | S1B | **during / peak** |
| 2020-10-23 | S1A | receding |
| 2020-10-29 | S1B | receding |
| 2020-11-04 | S1A | **post** |

Other tracks over the AOI (also VV+VH): rel. orbit 99 ascending (Oct 4, 10, 16, 22, 28), rel. orbit 164 and 91 descending. Available as extra held-out geometry if needed.

Each RTC item is a full slice (~28,000 × 21,500 px); the AOI will be windowed out with rasterio using the polygon above.

## Pre-processing pipeline decision

**Chosen pipeline for everything: Planetary Computer Sentinel-1 RTC.**

- Product: gamma-nought (γ⁰), radiometrically terrain corrected, 10 m, linear power units in the COGs. We convert to dB ourselves (`10·log10`) with a floor at −50 dB.
- No speckle filter applied by the provider. Speckle filtering is treated as an experiment (Level 2/3), applied identically or not at all.

**Sen1Floods11 pre-processing** (from the dataset paper, Bonafilia et al. 2020, CVPR Workshops): Sentinel-1 GRD exported from Google Earth Engine's `COPERNICUS/S1_GRD` collection — that collection is orbit-corrected, thermally corrected, radiometrically calibrated to **sigma-nought (σ⁰)**, terrain-corrected with SRTM, and stored in **dB**. Chips are 512 × 512 at 10 m, bands VV, VH.

**Known mismatch:** σ⁰ (benchmark) vs γ⁰ (RTC for Cambodia). On flat terrain the difference is small and roughly constant; on slopes it is not. Banteay Meanchey is mostly flat lowland, but the rule from Section 5 applies: **measure the switch effect before drawing conclusions about rice** (planned for Level 4, step 2 — run the same Sen1Floods11 Mekong chips' footprints through the RTC pipeline for the 2018 date and compare thresholds).

## Label origins (Sen1Floods11)

| Folder | How made | Use |
| --- | --- | --- |
| `HandLabeled/LabelHand` | Hand-drawn by analysts from S1 + S2, 446 chips, 11 events + Bolivia. Classes: 0 = no water, 1 = water, −1 = no data / uncertain | **Test and validation. Primary training set** |
| `HandLabeled/S1OtsuLabelHand` | Otsu threshold on S1 VH, over the hand-labelled chips | Level 1 comparison only — this *is* the baseline method. Never a label |
| `HandLabeled/JRCWaterHand` | JRC GSW permanent water | Tier D reference |
| `WeaklyLabeled/S1OtsuLabelWeak` | Otsu threshold on S1 VH (`VH_thresh` per event in metadata, e.g. Cambodia −23.06 dB) | **Never for evaluation.** Carries the exact "dark = water" bias under study |
| `WeaklyLabeled/S2IndexLabelWeak` | Optical water index threshold on S2 | Not radar-biased, but weak. Optional extra training only, reported separately |

## Cambodia inside Sen1Floods11 — leakage rule

Event ID 4, "Mekong" chips: Sentinel-1 5 Aug 2018, ascending, rel. orbit 26. **30 hand-labelled chips**, 1,353 weak chips.

The official split scatters the 30 Mekong chips as 18 train / 6 valid / 6 test. Per rule 8 (no leakage) and rule 5 (held-out region), **this project re-splits by event**: all 30 Mekong hand chips are held out as the Cambodia test set; the remaining 10 events (+ Bolivia) form train/valid. The 1,353 Mekong weak chips are excluded from training entirely so the model never sees Cambodian imagery before test time.

Hand-labelled chip counts per event (from split CSVs): Ghana 53, India 68, Mekong 30, Nigeria 18, Pakistan 28, Paraguay 67, Somalia 26, Spain 30, Sri-Lanka 42, USA 69, Bolivia 15.

## Open items carried into Level 0

1. Count flooded-cropland pixels per event after overlaying WorldCover (the number that decides whether the hypothesis test is powered).
2. Confirm the exact class encoding and no-data value in `LabelHand` by reading the files.
3. Confirm RTC COG units (linear vs dB) by reading one scene's metadata and value range.
