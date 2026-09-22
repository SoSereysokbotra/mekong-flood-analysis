# Level 0 — Sen1Floods11 inventory

**Date:** 21 September 2026
**Script:** `scripts/level0_inventory.py` → `docs/level0_inventory.csv`
**Figure:** `scripts/plot_sample_chip.py` → `docs/figures/level0_mekong_chip.png`

## Deliverable check

- [x] Radar chips load and display (VV, VH in dB, 512 × 512, EPSG:4326)
- [x] Hand labels decoded: 1 = water, 0 = no water, −1 = no data. Some chips are all −1 or all 0 (no flood present); kept, they contribute true negatives
- [x] ESA WorldCover 2020 overlaid on every chip (0 chips with > 10 % nodata)
- [x] Flooded-cropland pixel counts known per event and per split

## The number that matters

| Split | Chips | Flooded open water | **Flooded cropland** | Flooded vegetation | Flooded built | Crop share of flood |
| --- | --- | --- | --- | --- | --- | --- |
| train (8 events) | 368 | 2,687,401 | 1,887,610 | 2,009,731 | 6,541 | 27.1 % |
| valid (Spain + Nigeria) | 48 | 531,143 | 765,131 | 506,882 | 9,375 | 39.0 % |
| **test (Mekong, held out)** | 30 | 516,519 | **654,764** | 504,608 | 1,317 | 38.1 % |

**Conclusion: the hypothesis test is powered.** Flooded cropland is not a rare class — it is the single largest flood stratum in the Cambodia test set (38 % of flood pixels, more than open water), and there are 1.89 M training pixels of it across eight other events.

*Split note (22 Sep 2026):* the table uses the event-based split adopted at Level 1 (valid = Spain + Nigeria). The first version of this note used the official Sen1Floods11 chip-level partition for train/valid (249 / 167), which shares scenes across splits; test was Mekong in both. There is no need to add Kuro Siwo or UrbanSARFloods for Levels 1–3.

Per event (crop share of flood): Somalia 69 %, Pakistan 53 %, India 42 %, Nigeria 40 %, Spain 38 %, Mekong 38 %, USA 35 %, Ghana 24 %, Sri-Lanka 16 %, Paraguay 3 %, Bolivia 0 %. Bolivia and Paraguay are forest / wetland floodplains — useful as *negative* controls for cropland-specific behaviour.

## Caveats to carry forward

1. **WorldCover is 2020; events are 2016–2019.** Cropland is a stable class, but a field that was cropland in 2018 and built-up in 2020 is mis-stratified. Effect is expected to be small; flooded-built counts are tiny everywhere, which is consistent with that.
2. **"Cropland" ≠ "rice".** In the Mekong chips it almost certainly is paddy; in Spain or USA it is not. Stratum 2 numbers mean *flooded cropland* and nothing more. Recorded for the evaluation plan.
3. **Early warning for Level 2.** In the chip with the most flooded cropland (`Mekong_1248200`), flooded cropland has median VV −18.8 dB / VH −29.1 dB versus dry cropland −8.5 / −14.9 dB, and flooded open water −18.0 / −26.1 dB. That is, **these flooded paddies look dark, like open water** — the "young / sparse rice, water dominates" condition from Section 7 Level 2, not the bright double-bounce case. Two implications:
   - Thresholding may already do well on much of the Cambodia test set. The Level 1 baseline must be reported per stratum before assuming the gap exists in this data.
   - The hand labels were drawn by analysts looking at S1 *and* S2. Bright, double-bounce flooded rice is exactly the case where an analyst looking at radar would be tempted to mark "not water". Whether the labels contain bright flooded vegetation at all is a Level 2 question: histogram VV/VH of stratum 2 across all 30 Mekong chips and look for a bright mode.
4. **Land type is assigned to every pixel, not just flooded ones** (`strata.land_type`). Per-land-type precision and IoU need false positives on *dry* cropland, so the inventory CSV carries both `flood_<land>` and `dry_<land>` columns. `flood_unknown` (WorldCover nodata under a flood pixel) is 0 in every split.
5. **DEM multi-tile mosaic (closed).** Copernicus DEM COGs on Planetary Computer declare no nodata value, so `WarpedVRT` reported the *whole* target grid as valid for the first tile and filled everything outside it with 0 m; the remaining tiles were then blocked. Any grid spanning a tile boundary was wrong. Fix: give float sources with no declared nodata `NaN` as nodata before warping. Verified on a native-resolution grid straddling lon 103.0 (west 11.6 m / east 11.5 m, zero NaN, zero zeros). The slowness of the earlier coarse test was unrelated: the COGs' overviews stop at 8×, so a 36× downsample falls back to fetching many 1024² blocks over HTTP. Read at native resolution and downsample locally if a coarse DEM is ever wanted.
6. **Extreme dB values** (VV up to +36.8, down to −87.5) occur in a few chips — probably bright targets / no-signal edges. Clip to [−50, +10] before histogramming; check whether the outliers coincide with label −1.

## Review

An independent review (Gemini, 21 Sep 2026, read-only) reproduced every number above to the pixel and every Step 0 STAC claim, and found nine issues, all fixed in commit `review:` (a second pass closed the remaining DEM edge case) — the substantive ones were: NaN-nodata handling in the raster mosaic (would have broken multi-tile DEM reads), `to_db` turning nodata into −50 dB (would have made RTC scene collars look flooded), the split CSVs not being fetched by the download script, and strata discarding land cover on dry pixels (would have blocked per-land-type precision/IoU).

## Next: Level 1

Otsu threshold on VH (the Sen1Floods11 authors' choice) and on VV, per chip and with a global threshold; score IoU / precision / recall per stratum on valid and on the Mekong test set. `S1OtsuLabelHand` is the authors' own Otsu output and will be compared against as a cross-check of the implementation.
