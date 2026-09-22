# Level 4, step 2 — The pre-processing switch, measured (plan rule 9)

**Date:** 22 September 2026
**Script:** `scripts/level4_pipeline_switch.py` → `results/level4/pipeline_switch.json`, `pipeline_switch_per_chip.csv`; experiment-log rows level4 / `test_sigma0`, `test_gamma0`
**Question:** Level 3 models were trained and tested on Sen1Floods11 chips (σ⁰, dB, Google Earth Engine). Level 4 must run on Planetary Computer RTC (γ⁰, linear → dB). If the *same 30 Mekong chips* are rebuilt from RTC for the *same acquisition* (S1B, 5 Aug 2018, orbit 26 ascending) and scored against the *same hand labels*, what changes?

All numbers below are copied from the files above.

## 1. The two products differ by more than a constant

| | VV | VH |
| --- | --- | --- |
| γ⁰ − σ⁰, median of chip medians | **+1.63 dB** | **+1.80 dB** |
| within-chip std of the difference | 2.95 dB | 3.66 dB |
| pixel correlation γ⁰ vs σ⁰ (as gridded) | 0.59 | 0.60 |
| pixel correlation after best 1–3 px shift (6 chips checked) | — | 0.85–0.93 |

The level offset (~+1.7 dB) is the expected γ⁰/σ⁰ difference on flat terrain (1/cos θ at ~35–40° incidence ≈ +0.9–1.1 dB) plus processing-chain differences. The low raw correlation is a **geolocation offset of 1–3 pixels (10–30 m), varying in direction from chip to chip** — the two products terrain-correct with different DEMs (SRTM vs Copernicus) and resample differently. It is inherent to the products, not to this project's warp. Because the hand labels were drawn on the GEE grid, every method loses some edge pixels when scored on the RTC grid; that penalty is shared and small compared with what follows.

## 2. Effect on the Level 1 baseline and Level 3 models

Same chips, same labels, same pixels (pixels without RTC coverage excluded from both). Sub-strata defined on the σ⁰ VH as at Level 3.

| Method | Input | all IoU | crop IoU | crop prec | crop recall | bright crop | bright veg | dark | open water |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VH threshold (Level 1 baseline) | σ⁰ | 0.765 | 0.740 | 0.789 | 0.924 | 0.000 | 0.000 | 1.000 | 0.990 |
| | γ⁰ | 0.727 | 0.718 | 0.876 | 0.800 | 0.342 | 0.280 | 0.838 | 0.971 |
| U-Net VV-only (control) | σ⁰ | 0.863 | 0.881 | 0.975 | 0.901 | 0.408 | 0.402 | 0.941 | 0.996 |
| | γ⁰ | 0.767 | 0.788 | 0.976 | 0.804 | 0.317 | 0.284 | 0.844 | 0.982 |
| **U-Net VV+VH cropland-weighted (selected)** | σ⁰ | 0.820 | 0.768 | 0.786 | 0.971 | 0.714 | 0.707 | 0.993 | 0.997 |
| | **γ⁰** | **0.138** | **0.178** | 0.741 | **0.190** | 0.172 | 0.182 | **0.191** | **0.011** |

**The selected model does not survive the switch.** On γ⁰ it labels 1 % of open water as water. The threshold and the VV-only U-Net degrade by 4–10 IoU points; the selected model loses 68.

Diagnostic (not logged, no decision taken from it): subtracting the median per-band offset lifts the selected model only to all-IoU 0.42; a generous −3 dB to 0.51 — still far from 0.82. The failure is not a simple level shift that a calibration constant removes. The model learned a decision surface tied to one processing chain's absolute intensities and speckle/resampling texture. The VV-only U-Net, trained with plain cross-entropy, is far more robust (0.77 → 0.80 with the offset).

## 3. What this means

1. **The Level 3 "confirmed" result stands for what it claims — and no more.** Under the frozen plan, on the benchmark's own processing, the model does what §7 requires. The plan (§8) already forbids presenting it as a Cambodia harvest-stage result. Now it also cannot be presented as *transferable to a different processing chain*. That is rule 9 doing its job: this would otherwise have shown up at Level 4 as "the model fails on Cambodia", and been misread as a statement about rice.
2. **Applying `unet_vvvh_cropw` to the October 2020 RTC scenes as-is would be meaningless.** Any Cambodia map it produced would be wrong for reasons that have nothing to do with flooded vegetation.
3. **The plan's own remedy applies:** "Use one pre-processing pipeline for training and testing wherever possible." RTC exists on Planetary Computer for the exact date and track of **10 of the 11** Sen1Floods11 events (all but Paraguay, whose 31 Oct 2018 orbit-68 scene is absent from the archive). The benchmark can be rebuilt on the Level 4 pipeline.

## 4. Options

| | What | Cost | What it gives |
| --- | --- | --- | --- |
| **A (recommended)** | Rebuild all chips from RTC γ⁰ (10 events; Paraguay dropped from train, 368 → 301 chips). Retrain the Level 3 ladder on the RTC chips, under the same frozen criteria, splits, controls and selection rule, as **evaluation plan v1.1** (changelog: input pipeline changed to RTC; reason: this measurement). Select on valid, score test once. | RTC fetch ~1 h (11 STAC searches), Colab ~1 h, one more selection + test cycle | One pipeline end to end. Whatever passes §7 on RTC test is directly applicable to Cambodia. |
| B | Keep the σ⁰ models; go to Cambodia with only the threshold and the VV-only U-Net (the robust ones), drop the selected model. | Nothing | A weaker, non-hypothesis-targeting model in Level 4; the Level 3 headline model never reaches Cambodia. |
| C | Calibrate γ⁰ → σ⁰ per band and use the selected model anyway. | Trivial | Shown above not to work (0.42–0.51 IoU). Rejected. |

Option A also removes the geolocation-mismatch penalty for the Cambodia stage (Tier B labels will be drawn on the RTC grid).

## Deliverable check

- [x] Switch effect measured before any Cambodia conclusion (rule 9)
- [x] Cause identified: ~+1.7 dB level offset + 1–3 px geolocation differences between GEE σ⁰ and PC RTC γ⁰
- [x] Consequence stated: the selected σ⁰ model is unusable on RTC; the VV-only model and threshold are usable with a 4–10 point loss
- [ ] Decision on option A recorded (owner)
