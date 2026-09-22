# Level 3 — Hypothesis test: results against the frozen evaluation plan

**Date:** 22 September 2026
**Plan in force:** `evaluation_plan.md` v1.0, frozen at commit `2f33bcf` (09:04). Selection recorded at commit `f61a907` (13:19). Test scored once after that.
**Runs:** `results/experiment_log.csv`, level `level3`; per-run artefacts under `results/level3/<run>/`
**Scripts:** `scripts/level3_train.py`, `level3_pixel_control.py`, `level3_test.py`, `plot_level3.py`
**Figures:** `docs/figures/level3_test.png`, `level3_valid.png`, `level3_per_chip.png`

All numbers are copied from `results/level3/<run>/metrics_{valid,test}.json`. If a number here disagrees with those files, the files are right.

## Outcome: **Confirmed** (evaluation_plan v1.0 §7)

Selected model: `unet_vvvh_cropw` — U-Net from scratch (1.9 M params), inputs VV + VH, cross-entropy with labelled-flood pixels on cropland and vegetation weighted ×4, 30 epochs, best epoch 13 on valid. Held-out Mekong split, 30 chips:

| Criterion | Required | Result | |
| --- | --- | --- | --- |
| B — `cropland_bright` recall | ≥ 0.50 | **0.714** | pass |
| V — `vegetation_bright` recall | ≥ 0.50 | **0.707** | pass |
| P — cropland precision | ≥ 0.75 | **0.786** | pass (margin 0.036) |
| I — all IoU | ≥ 0.765 | **0.820** | pass |
| D — `cropland_dark` recall | ≥ 0.95 | **0.993** | pass |
| Beats per-pixel control on B | by ≥ 0.10 | 0.714 vs 0.049 (+0.665) | pass |

Every condition of the confirmed row is met. No condition was changed after freezing; no test number was seen before the selection commit.

## Full comparison on the held-out split

| Run | Role | B bright crop | V bright veg | P crop prec | crop IoU | crop recall | I all IoU | D dark rec | veg recall | crop FP px | crop FN px |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `otsu_vh_global` | Level 1 baseline | 0.000 | 0.000 | 0.789 | 0.740 | 0.924 | 0.765 | 1.000 | 0.738 | 162,175 | 49,937 |
| `otsu_vv_global` | free alternative | 0.387 | 0.435 | 0.879 | 0.818 | 0.921 | 0.754 | 0.965 | 0.815 | 82,685 | 51,726 |
| `pixel_logreg` | control §6.2 | 0.049 | 0.046 | 0.886 | 0.811 | 0.906 | 0.814 | 0.977 | 0.716 | 76,665 | 61,633 |
| `pixel_mlp` | control §6.2 | 0.034 | 0.036 | 0.853 | 0.776 | 0.897 | 0.793 | 0.968 | — | — | — |
| `unet_vv_ce` | control §6.3 | 0.408 | 0.402 | **0.975** | **0.881** | 0.901 | **0.863** | 0.941 | 0.779 | 14,921 | 64,999 |
| **`unet_vvvh_cropw`** | **selected** | **0.714** | **0.707** | 0.786 | 0.768 | **0.971** | 0.820 | 0.993 | **0.915** | 173,212 | 18,675 |

Per-chip `cropland_bright` recall for the selected model (16 chips with > 500 bright px): median 0.708, min 0.202, max 0.961 (`level3_per_chip.png`). The result is not carried by one chip.

## What the controls establish

1. **The gain is spatial context, not a better threshold.** Per-pixel classifiers on (VV, VH, VV−VH, slope) — the best possible "threshold" in that feature space — recover 3–5 % of bright flooded cropland. The U-Net with the same two radar bands recovers 71 %. Level 2 predicted this: per-pixel intensity had AUC ≈ 0.5 for bright flooded vs dry cropland on train.
2. **Dual-pol matters.** VV-only U-Net: 0.408 / 0.402. VV + VH: 0.714 / 0.707. The +0.30 is the VH channel, which is also where Level 1 showed the two polarisations disagree on exactly these pixels.
3. **The cropland-weighted loss is what crossed the bar.** On valid, plain CE / Dice+CE / focal / no-aug / +slope / pretrained encoder all scored 0.17–0.36; the ×4 weight on flood-on-cropland/vegetation pixels scored 0.564 and was consistently above the others across its last ten epochs (`level3_valid.png`). The plan's speculative addition (Section 7, Level 3: "test cropland-weighted loss") turned out to be the decisive one.

## What "confirmed" does *not* mean — read before citing this

1. **This is not a result about Cambodian rice at harvest stage.** The test scene is 5 Aug 2018: vegetative rice, only 7 % of labelled flooded cropland bright (`docs/level1_baseline.md`). The 50 k bright cropland pixels the model recovers are real, but the October double-bounce case the project is motivated by is *not in this test set*. Plan §8 forbids presenting it that way. That claim needs Level 4 with Tier B labels on 14 Oct 2020.
2. **The selected model trades precision for bright recall.** It has 173 k cropland false positives on test — more than the Level 1 baseline (162 k) and 12× the VV-only U-Net (15 k). Its cropland precision (0.786) clears the frozen floor by 0.036. The VV-only U-Net is the *better general flood map* (all IoU 0.863, cropland IoU 0.881, precision 0.975); the selected model is the better *bright-vegetation detector*. The frozen criteria chose the latter, deliberately. An operational product would likely want the VV-only map with the selected model's bright-vegetation detections added — a Level 7 decision, not a Level 3 one.
3. **Valid is small and noisy.** Two events, 48 chips, 94 k bright pixels; every run's selection score moved by 0.1–0.2 between adjacent epochs. Selection was nevertheless unambiguous (0.564 vs 0.361) and the test result is far from the criteria's edge on B, V, I and D. On P it is not.
4. **Eight training events.** The pretrained ResNet-18 encoder peaked at epoch 1 and degraded — overfitting to eight scenes. The from-scratch U-Net at 1.9 M parameters was the right size for this data.
5. **Precision margin is thin (0.036).** A different seed could plausibly land below 0.75. Rule 5 of the plan (held-out region) is satisfied, but a multi-seed run would be needed to call the precision result robust. Not done here; recorded as a limitation.

## What was run, in order (auditable in `results/experiment_log.csv`)

1. Per-pixel controls (local): `pixel_logreg`, `pixel_mlp` — valid rows 22 Sep.
2. `unet_vvvh_ce`, `unet_vv_ce` (local RTX 3050, ~28 min each), then the remaining six on Colab T4 via `notebooks/colab_level3.ipynb`, pushed as commit `729b3ea`. Same script, same configs, same cache.
3. `--select` → `unet_vvvh_cropw` → commit `f61a907`.
4. `--run` on the selected model and the three controls; four test rows, nothing else.

Compute: total < 6 GPU-hours. No paid compute.

## Level 3 deliverable check

- [x] Results reported against the frozen plan, per land type, with controls
- [x] Outcome stated: **Confirmed**, with the scope limits above
- [x] Predictions saved (`results/level3/<run>/pred_test/`) for Level 4 comparison

## Next: Level 4

Apply `otsu_vh_global`, `unet_vv_ce` and `unet_vvvh_cropw` to Banteay Meanchey, 26 Sep / 14 Oct / 1 Nov 2020 (track 164). Before any conclusion: measure the σ⁰→γ⁰ pipeline switch on the Mekong chips' footprints (plan rule 9). Validation: Tier B hand labels (protocol in `data/labels/LABELLING_PROTOCOL.md`), Tier D JRC, Tier E OCHA figures.
