# Level 2 — Failure analysis of the thresholding baseline

**Date:** 22 September 2026
**Baseline analysed:** `otsu_vh_global` (VH < −19.65 dB), predictions saved at Level 1
**Scripts:** `scripts/level2_failure_analysis.py` → `results/level2/{failure_taxonomy.json, failure_per_chip.csv, mekong_bright_per_chip.csv, joint_hist.npz, separability.json}`; `scripts/plot_level2.py` → `docs/figures/level2_{taxonomy,joint,examples}.png`
**Ancillary layers:** Copernicus DEM GLO-30 on every chip (`io.dem_chip`, slope in degrees with pixel spacing converted to metres — chips are EPSG:4326), JRC permanent water shipped with each chip, WorldCover 2020 land type.

All numbers below are copied from the files above.

## 1. Where the baseline fails

Pixel counts of the selected baseline, per split. Categories are mutually exclusive, first match wins (see the script docstring for the order).

### False positives — predicted water, labelled dry

| Category | Physical cause | train (11.36 M FP) | valid (1.60 M) | **test (0.27 M)** |
| --- | --- | --- | --- | --- |
| dry cropland, flat | wet / ploughed / harvested soil is smooth → dark | 42.0 % | 37.8 % | **58.9 %** |
| dry vegetation, flat | short grass / wetland vegetation on wet ground | 41.7 % | 19.7 % | 31.1 % |
| built-up / bare | roads, airstrips, sand: specular | 9.2 % | 33.9 % | 2.8 % |
| terrain (slope ≥ 8°) | radar shadow on slopes facing away from the sensor | 5.0 % | 7.4 % | 5.7 % |
| WorldCover water / JRC permanent, label dry | label vs. reference disagreement | 2.0 % | 1.1 % | 1.5 % |

The FP problem is dominated by **dark dry land**, not by terrain. On train the baseline produces twice as many FP as TP (11.4 M vs 5.5 M): a single VH threshold fitted on pooled training pixels sits badly for events like Paraguay and Bolivia whose dry fields and wetlands are dark. On the Cambodia test set FP are far fewer (0.27 M vs 1.53 M TP), so **one global threshold does not transfer across events**, and the test set happens to be one where it works. Terrain shadow is real (`level2_examples.png`, row 1: India hills) but small; the DEM channel in Level 3 addresses a 5–7 % slice of FP, not the bulk.

### False negatives — labelled water, predicted dry

Every FN of a VH threshold is VH-bright by construction, so the categories are land types. Each is split by whether VV is also bright (no single-band rule can recover it) or VV is dark (a dual-pol rule could).

| Category | train (1.41 M FN) | valid (0.32 M) | **test (0.19 M)** | of which VV-dark on test |
| --- | --- | --- | --- | --- |
| bright flooded cropland | 47.9 % | 29.6 % | **25.8 % (49,937 px)** | 39 % |
| bright flooded vegetation | 41.9 % | 55.8 % | **68.2 % (132,130 px)** | 44 % |
| rough open water (wind) | 5.3 % | 2.6 % | 2.6 % | 42 % |
| built / other | 4.9 % | 12.0 % | 3.5 % | — |

**On the Cambodia test set, 94 % of what thresholding misses is flooded vegetation in the broad sense** (cropland + tree/grass/wetland), 182 k pixels. The plan's hypothesis is phrased as "flooded vegetation"; rice is the motivating case but the measurable class in these labels is wider, and the vegetation part (flooded forest / grassland around the Tonle Sap floodplain) is 2.6× larger than the cropland part. Both sub-strata are therefore tracked (`cropland_bright` already in `metrics.py`; `vegetation_bright` added with this level).

## 2. Can intensity alone separate bright flooded cropland from dry cropland?

`results/level2/separability.json`: single-feature AUC (Mann–Whitney) for *bright* flooded cropland (VH ≥ −19.65) against dry cropland, 2,000 px sampled per chip.

| Split | n bright flood / n dry | AUC VV (darker = flood) | AUC VH | AUC VV−VH (higher = flood) |
| --- | --- | --- | --- | --- |
| train | 296 k / 736 k | **0.529** | 0.508 | 0.456 |
| valid | 62 k / 96 k | 0.542 | 0.490 | 0.424 |
| test | 34 k / 60 k | 0.719 | 0.669 | 0.422 |

On the training events the bright flooded population is **inseparable from dry cropland by per-pixel intensity** (AUC ≈ 0.5 on every band and on the ratio; `level2_joint.png` shows the bright flooded mass sitting inside the dry cluster at VV −10 / VH −17). The VV−VH ratio goes the *wrong* way for the double-bounce expectation (flooded pixels have relatively higher VH, not lower).

This is the plan's stated early warning ("if there is no visible difference in any input channel, that is an early warning that ML may not help — record it"). Recorded. What it implies for Level 3:

- A per-pixel classifier on (VV, VH) cannot solve this. **The only lever a U-Net has is spatial context** — a bright field surrounded by dark water, field-shaped patches, texture. Any Level 3 gain on `cropland_bright` is a spatial-context result, and the experiment design should include a per-pixel model (logistic regression on VV, VH, VV−VH, slope) as a control to prove that.
- Temporal change (pre-event scene) is the other lever, and it is *not* available in Sen1Floods11 (one date per event). It is available for Cambodia at Level 4 (26 Sep → 14 Oct 2020). This is a reason to expect Level 4 to differ from Level 3.

## 3. Where the bright Cambodia pixels are

`results/level2/mekong_bright_per_chip.csv`: the 49,937 bright flooded-cropland pixels are spread over the 30 chips, not concentrated: the top chip has 11,560, seven chips have > 2,000. Two small-paddy chips (`Mekong_474783`, `Mekong_1149855`) have 26–36 % of their flooded cropland bright — the highest fractions — with VV medians (−10.0, −10.1 dB) within 2 dB of dry cropland. Those are the closest thing in this dataset to the mature-rice double-bounce case, and they are worth looking at against the S2 chip at Level 3.

## 4. Crop stage: why August 2018 is the wrong month, and October 2020 is the right one

Sources: FAO/GIEWS Cambodia country brief and reports — main wet-season rice is sown late May–July, transplanted through September, harvested from late November ([GIEWS KHM archive](https://www.fao.org/giews/countrybrief/country/KHM/pdf_archive/KHM_Archive.pdf), [GIEWS 11/01](https://www.fao.org/4/y2723e/pays/cmb0111e.htm)).

| Scene | Date | Weeks after transplanting (typical) | Stage | Expected radar response of a flooded field |
| --- | --- | --- | --- | --- |
| Sen1Floods11 Cambodia (test) | 5 Aug 2018 | 4–8 | vegetative; short, sparse | water dominates → **dark** (what Level 1 measured: one dark mode at −29 dB) |
| Anchor event (Level 4) | 14 Oct 2020 | 12–18 | reproductive / ripening; tall, dense | double bounce → **bright**, VH especially |

So the near-absence of bright flooded rice in the Cambodia test labels is not evidence that the phenomenon is rare in Cambodia — it is what the crop calendar predicts for an August scene. The October event is where the motivating case should actually appear. This is the strongest argument for Route B (Tier B hand labels on 14 Oct 2020, protocol in `data/labels/LABELLING_PROTOCOL.md`), and it must be said plainly in the final write-up: **Level 3 tests the hypothesis on other countries' bright floods; only Level 4 with Tier B labels tests it on Cambodian rice.**

Two caveats: (a) crop calendars vary by province and by early/late varieties; Banteay Meanchey grows some early-season rice harvested in October, so an October scene will contain a mix of stages — that mix should be recorded per Tier B tile from the optical imagery; (b) wind: double bounce needs calm water, and the 06:00-local descending pass is usually calmer than the 18:20 ascending one — another reason track 164 is the primary.

## 5. Consequences for the evaluation plan

From Level 1 and Level 2, the numbers that fix X and Y (all from the selected baseline on the held-out Mekong split, `results/level1/otsu_vh_global/metrics_test.json`):

| Quantity | Baseline (test) | Free single-band alternative (`otsu_vv_global`, test) |
| --- | --- | --- |
| `cropland_bright` recall | 0.000 | 0.387 |
| cropland precision | 0.789 | 0.879 |
| cropland recall | 0.924 | 0.921 |
| `cropland_dark` recall | 1.000 | 0.965 |
| vegetation recall | 0.738 | 0.815 |
| all IoU | 0.765 | 0.754 |

Points that shape X and Y:
1. Baseline bright recall is 0 by construction, so "improves by X points" is measured from zero and is trivially gamed by over-detection. A precision floor is not optional.
2. A VV threshold already recovers 39 % of bright cropland at *higher* precision than the baseline. A model that reaches 0.35 bright recall has achieved nothing a second threshold would not. The confirmed bar must clear that.
3. Intensity is non-separable on train (AUC 0.5). A meaningful gain is therefore hard; the rejected outcome is a live possibility and is acceptable.
4. The Cambodia bright population is small (50 k px, ~30 chips). Report per-chip recall alongside the pooled number so a single chip cannot carry the result.

Proposed values are in `evaluation_plan.md` (draft). They are frozen by a dedicated commit once agreed.

## Level 2 deliverable check

- [x] Written analysis with example images per failure type (`level2_examples.png`: terrain, dark dry cropland, bright flooded cropland, rough water)
- [x] Failure conditions recorded (land type, slope, VV/VH state) — crop stage and wind recorded for the two Cambodia scenes in §4; per-chip crop stage will be recorded at Level 4 from optical imagery
- [x] "Do flooded-vegetation pixels look different in VH than VV?" answered: not by intensity on train (AUC ≈ 0.5); partially on test (0.67–0.72)
- [x] X and Y proposed from own results; `evaluation_plan.md` drafted, freeze pending
