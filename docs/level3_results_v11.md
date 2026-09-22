# Level 3 (plan v1.1, RTC) — Hypothesis test on one pre-processing pipeline

**Date:** 22 September 2026
**Plan in force:** `evaluation_plan.md` **v1.1** (commit `bd67b60`) — identical to the frozen v1.0 except that every split now uses Planetary Computer RTC γ⁰, for the measured reason in `docs/level4_pipeline_switch.md`. Selection recorded at `3445a92` (23:08); test scored once after that.
**Runs:** `results/experiment_log.csv`, level `level3_rtc`; artefacts under `results/level3_rtc/<run>/`
**v1.0 results** (σ⁰ inputs) remain in `docs/level3_results.md` and `results/level3/`. They are a different experiment and are not compared as if they were the same one.

All numbers are copied from the metrics files. If a number here disagrees with those files, the files are right.

## Outcome: **Confirmed**

Selected model: `unet_vvvh_cropw` — U-Net from scratch (1.9 M params), VV + VH, cross-entropy with labelled-flood pixels on cropland and vegetation weighted ×4, best epoch 22 of 30 on valid. Held-out Mekong split, 30 chips:

| Criterion | Required | Result | |
| --- | --- | --- | --- |
| B — `cropland_bright` recall | ≥ 0.50 | **0.790** | pass |
| V — `vegetation_bright` recall | ≥ 0.50 | **0.754** | pass |
| P — cropland precision | ≥ 0.75 | **0.827** | pass (margin 0.077) |
| I — all IoU | ≥ 0.765 | **0.797** | pass |
| D — `cropland_dark` recall | ≥ 0.95 | **0.997** | pass |
| Beats per-pixel control on B | by ≥ 0.10 | 0.790 vs 0.239 (+0.551) | pass |

Per-chip B (20 chips with > 500 bright px): median 0.765, min 0.312, max 0.981. Not carried by one chip.

## Full comparison on the held-out split (RTC inputs)

| Run | Role | B | V | P | I | D | crop IoU | crop recall | open water | vegetation | crop FP px |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `otsu_vh_global` on γ⁰ | Level 1 threshold | 0.342 | 0.280 | 0.876 | 0.727 | 0.838 | 0.718 | 0.800 | 0.971 | — | — |
| `pixel_logreg` | control §6.2 | 0.239 | 0.216 | 0.869 | 0.756 | 0.998 | 0.751 | 0.846 | 0.981 | 0.676 | — |
| `pixel_mlp` | control §6.2 | 0.194 | 0.148 | 0.834 | 0.739 | 0.999 | 0.718 | 0.837 | 0.982 | 0.646 | — |
| `unet_vv_ce` | control §6.3 | 0.628 | 0.598 | **0.948** | **0.806** | 0.973 | **0.861** | 0.904 | 0.998 | 0.813 | 32,752 |
| **`unet_vvvh_cropw`** | **selected** | **0.790** | **0.754** | 0.827 | 0.797 | **0.997** | 0.797 | **0.955** | 0.998 | **0.897** | 130,451 |

(The threshold row is from `results/level4/pipeline_switch.json`, the same chips scored on γ⁰.)

## Sensitivity: does the verdict depend on how "bright" is defined?

**A discrepancy found while writing this up, reported rather than smoothed over.** Plan v1.1 §2 states that the bright sub-strata stay pinned to the σ⁰ VH threshold (−19.65 dB) so v1.0 and v1.1 cover the same pixels. The code instead takes the VH of whichever pipeline the run uses. Because γ⁰ sits ~1.8 dB higher, the v1.1 bright class is 2.6× larger: 131,132 cropland pixels instead of 49,937.

`scripts/level3_bright_definition_check.py` re-scores the *saved test predictions* (no retraining, no reselection) under both definitions:

| Run | Definition | B (n) | V (n) | D |
| --- | --- | --- | --- | --- |
| **`unet_vvvh_cropw`** | RTC VH (as reported) | **0.790** (131,132) | **0.754** (208,248) | 0.997 |
| | σ⁰ VH (as the plan text says) | **0.716** (49,937) | **0.730** (132,130) | 0.975 |
| `unet_vv_ce` | RTC VH | 0.628 | 0.598 | 0.973 |
| | σ⁰ VH | 0.569 | 0.608 | 0.932 |
| `pixel_logreg` | RTC VH | 0.239 | 0.216 | 0.998 |
| | σ⁰ VH | 0.425 | 0.382 | 0.881 |
| `pixel_mlp` | RTC VH | 0.194 | 0.148 | 0.999 |
| | σ⁰ VH | 0.411 | 0.345 | 0.873 |

**Every §7 criterion passes under both definitions** (σ⁰ definition: B 0.716, V 0.730, D 0.975, best control 0.425 → margin 0.291). P and I do not depend on the definition. The verdict is robust; the discrepancy changes the numbers, not the conclusion. The plan text will be corrected to match the code in the next version, with this check as the record.

## What the controls establish

1. **Spatial context, not a threshold.** The best per-pixel classifier on (VV, VH, VV−VH, slope) reaches B 0.239 (0.425 under the σ⁰ definition); the U-Net on the same two bands reaches 0.790 (0.716). The margin is smaller than in v1.0 because the per-pixel controls do *better* on RTC — γ⁰ terrain correction evidently makes intensity more informative — which raises the bar rather than lowering it.
2. **Dual-pol matters.** VV-only U-Net 0.628 → VV+VH 0.790.
3. **The cropland-weighted loss is decisive again.** On valid it scored 0.690 against 0.600 (Dice+CE), 0.598 (pretrained ResNet-18), 0.551 (focal), 0.533 (VV-only), 0.380 (no augmentation), 0.346 (plain CE), 0.326 (+slope).

## Comparison with the v1.0 run — and why it is not a like-for-like table

Both runs selected the same configuration by the same rule, and both reached "Confirmed". Beyond that, the two are different experiments: different inputs, 301 vs 368 training chips, and a bright class of different size. Directionally:

| | v1.0 (σ⁰) | v1.1 (RTC γ⁰) |
| --- | --- | --- |
| B / V (as reported) | 0.714 / 0.707 | 0.790 / 0.754 |
| Cropland precision | 0.786 (margin 0.036) | 0.827 (margin 0.077) |
| Cropland FP px | 173,212 | 130,451 |
| Per-pixel control B | 0.049 | 0.239 |
| Transfers to the Cambodia scenes? | **No** (all IoU 0.820 → 0.138 on γ⁰) | **Yes, by construction** |

The v1.1 model is better on the metrics that matter here *and* is the only one that can be applied at Level 4.

## Limits that still stand

1. **Not a harvest-stage rice result.** The test scene is 5 Aug 2018 — vegetative rice. Plan §8 forbids presenting this as a statement about Cambodian rice in October. Only Level 4 with Tier B labels can support that.
2. **The selected model over-detects on dry cropland**: 130 k false positives against the VV-only U-Net's 33 k. The VV-only model is the better *general* flood map (crop IoU 0.861, precision 0.948, all IoU 0.806); the selected model is the better *bright-vegetation detector* (B +0.16, vegetation recall 0.897 vs 0.813). Both are carried to Level 4.
3. **One seed.** Not repeated; the precision margin is healthier than v1.0's but still unverified across seeds.
4. **Paraguay dropped** (no RTC for its acquisition): 301 training chips instead of 368, and the project lost its main low-cropland negative control.

## Next: Level 4 proper

Apply `otsu_vh_global`, `unet_vv_ce` and `unet_vvvh_cropw` (all v1.1) to Banteay Meanchey RTC scenes on track 164: 26 Sep (pre), 14 Oct (peak), 1 Nov (post). Validate with Tier D (JRC permanent water), Tier E (OCHA figures), and Tier B hand labels once drawn (`data/labels/LABELLING_PROTOCOL.md`).
