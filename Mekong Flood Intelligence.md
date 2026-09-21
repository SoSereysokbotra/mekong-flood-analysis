# Mekong Flood Intelligence — Project Document

**Author:** Sobotra
**Status:** Planning (not yet started)
**Version:** 3
**Last updated:** 21 September 2026

---

## 1. One-sentence description

An Earth-observation system that detects flooded areas in Cambodia from radar satellite data, with a focus on flooded rice fields — a case that current operational flood maps are known to miss.

---

## 2. Why this project exists

### The problem

Cambodia floods almost every year. In October 2020, roughly 156,000 households across 14 provinces were affected. Among the damage: 51,133 houses, 439 schools, and **137,160 hectares of rice fields**.

That last number is the point of this project.

### Why normal satellite photos don't work

Floods in Cambodia happen during monsoon season. Monsoon season means clouds. Optical satellites (Sentinel-2, Landsat) take ordinary photographs — and photographs cannot see through cloud.

So at the exact moment you most need to see the ground, optical imagery is mostly useless.

### Why radar is the answer

Radar satellites (Sentinel-1) send their own signal down and measure what bounces back. Cloud does not block it. Neither does darkness. This is why professional flood mapping organisations use radar.

**How radar finds water:** smooth water reflects the radar signal away from the satellite, so almost nothing comes back. Water appears dark. Land appears bright. So: dark = water.

### The gap this project targets

That simple rule breaks in one important case.

When a rice field floods, the rice plants still stick up above the water. The radar signal bounces off the water surface, then off the rice stalk, then back to the satellite. This is called **double bounce**, and it makes flooded rice look *brighter* than dry rice — the opposite of what the rule expects.

This is not just noise. It is a **signal inversion**: the order of the classes flips. That matters later (see Section 6), because it means a model that learns "dark = flood" is not slightly wrong on rice fields — it is systematically wrong.

UNOSAT — the United Nations satellite centre — prints a warning on their own published flood maps stating that radar analysis may underestimate standing water in built-up and densely vegetated areas, because of how the radar signal scatters.

**So: the UN publicly acknowledges this limitation, and Cambodia's flood damage is dominated by exactly this land type.**

That gap is the project.

---

## 3. What makes this different from a student project

| Ordinary student project | This project |
| --- | --- |
| Uses a tutorial dataset | Uses real satellite data for a real disaster |
| Result is "it works" | Result is a measured score |
| Picks metrics after seeing results | Fixes evaluation criteria before training |
| One validation source | Several independent validation sources |
| Only success counts | A negative result is a valid outcome |
| Solves a solved problem | Targets a documented open limitation |

The differentiator is **honest measurement**.

---

## 4. The anchor event

**October 2020 Cambodia floods**

| Item | Detail |
| --- | --- |
| Dates | 1–21 October 2020 |
| Cause | Monsoon trough + Tropical Storm Linfa |
| Worst affected | Battambang, Banteay Meanchey, Pursat |
| Households affected | ~156,137 (as of 21 Oct) |
| Rice field damage | 137,160 hectares |

**Why this event:**

- Sentinel-1 radar was operating in 2020, so data is free (raw via Copernicus Data Space; ready-processed versions also exist — see Section 7, Step 0)
- Heavy rice-field involvement — the technical focus
- Sentinel Asia was activated (AHA Centre request) and produced flood maps for Banteay Meanchey and Kampong Thom
- Well documented in humanitarian reports

**Starting study area:** Banteay Meanchey province.

**Important:** the Sentinel Asia Web GIS for this event appears to be member-only. Map *images* may be public, but an image is not a flood polygon — you cannot compute pixel scores against a PNG without hand-digitising it. The project must **not** depend on this source. See Section 5.

---

## 5. Validation strategy

### Principle

No single data source is allowed to decide whether the project can succeed. If one website is locked, the project continues.

### Validation ladder

| Tier | Source | What it gives | Covers Cambodia? | Availability |
| --- | --- | --- | --- | --- |
| A | Benchmark ground truth (Sen1Floods11, Kuro Siwo, UrbanSARFloods) — **hand-made labels only** for testing | Pixel-level labels, real IoU | Possibly (Sen1Floods11 may include a Mekong event — verify) | Confirmed free |
| B | Own hand-labelled tiles over Banteay Meanchey | Pixel-level labels | Yes | Fully in your control |
| C | Cloud-free Sentinel-2 near the event date | Independent optical check | Yes | Opportunistic — may not exist |
| D | JRC Global Surface Water | Permanent and seasonal water reference | Yes | Confirmed free |
| E | Province-level affected figures (reports) | Rough sanity check only | Yes | Confirmed |
| F | Sentinel Asia / UNOSAT official products | Official comparison | Yes | **Unconfirmed** |

**Guaranteed today:** A, D, E. That is enough to run the whole project.
**Bonus if obtained:** C, F.

### How each tier is used

- **Tier A** — develop and compare methods where the correct answer is known. Main source of honest numbers.
- **Tier B** — the Cambodia-specific test. Labelling rules must be written down *before* labelling (what counts as flooded rice, how to mark uncertain pixels). Record an "uncertain" class rather than forcing a guess. If possible, have a second person label a small subset to check agreement.
- **Tier C** — optical sees flooded vegetation differently from radar, so it is a genuinely independent check on the rice question specifically.
- **Tier D** — used to separate new flooding from water that is always there (permanent rivers, normal Tonle Sap expansion). Not a flood label.
- **Tier E** — only to catch absurd results (e.g. your map says 5 km² flooded when reports describe tens of thousands of hectares).
- **Tier F** — compared if obtained; never required.

### Stratifying by land type

To measure performance on rice fields separately, you need to know which pixels are cropland. Benchmark flood labels usually only say "flood / not flood" — they do not say "flooded vegetation."

**Solution:** overlay a land-cover map (e.g. ESA WorldCover, which has a cropland class) on the flood labels. This splits results into:

- flooded open water
- flooded cropland / vegetation
- flooded built-up
- non-flooded

This is what makes the rice-field question measurable at all.

### Label quality warning

Not all labels are equal. Some benchmark datasets (Sen1Floods11 in particular) contain two kinds of labels:

- **Hand-made labels** — drawn by people. Smaller set, higher quality.
- **Automatic ("weak") labels** — generated by a program. Larger set. Some were made by thresholding the radar itself — i.e. using the rule "dark = water."

Radar-thresholded labels contain **the exact bias this project studies**. They miss flooded rice for the same reason thresholding does. A model trained on them will learn to miss flooded rice — because the labels told it to — and the project would wrongly conclude that the physics is the limit.

**Rules:**
1. Before using any label set, find out how it was made. Write it down.
2. **Test only on hand-made labels.** Never evaluate on labels generated by radar thresholding.
3. If weak labels are used for training, also train a model on hand-made labels only, and report both.

### Pre-processing consistency

The same place on the same day can give **different pixel values** depending on how the radar data was processed (for example sigma-nought vs gamma-nought, dB vs linear scale, with or without speckle filtering).

If the model is trained on data processed one way and applied to Cambodia data processed another way, it may fail for reasons unrelated to rice or double bounce.

**Rules:**
1. Use one pre-processing pipeline for training and testing wherever possible.
2. If pipelines must differ (e.g. benchmark vs Cambodia data), measure how much performance drops from the switch alone, before drawing conclusions about rice.
3. Speckle filtering is a choice, not an automatic fix: it reduces noise but blurs edges and can erase small flooded paddies. Apply it identically to all data, or test it as an experiment.

---

## 6. Hypothesis and evaluation plan

### Hypothesis

> Thresholding misses flooded vegetation because double bounce makes it bright. A segmentation model using dual-polarisation (VV + VH) and spatial context will recover a meaningful share of flooded-vegetation pixels that thresholding misses.

This is a reasonable hypothesis. **It is not guaranteed.** The signal inversion means a model may simply learn the same "dark = flood" bias from training data dominated by open water.

### Allowed outcomes

All three are legitimate results:

| Outcome | Meaning | Still valuable because |
| --- | --- | --- |
| Confirmed | Model recovers flooded vegetation reliably | You have a working method |
| Partial | Improves in some conditions but not others | You can describe *which* conditions — crop stage, water depth, season |
| Rejected | Model improves overall but not on flooded vegetation | Shows the limitation is physical, not just algorithmic — Level 2 explains why |

A rejected hypothesis with a clear explanation is a stronger result than a vague "3% improvement."

### Pre-registered evaluation rules

**These must be written down and fixed before Level 3 training begins.** Changing them after seeing results defeats the purpose.

1. **Report flooded-vegetation recall separately.** Never rely only on pooled scores. Flooded vegetation is a minority class; a model can ignore it completely and still look good overall.
2. **Primary metrics:** IoU and recall per land-type stratum (Section 5). Overall accuracy is not used — most pixels are dry land, so it is misleading.
3. **Why recall matters most:** missing a flooded village is worse than a false alarm.
4. **Success threshold:** before training, write down a specific target, e.g. *"flooded-vegetation recall improves by at least X points over the Level 1 baseline, while overall precision stays above Y."* Choose X and Y from Level 1 and Level 2 results, then freeze them.
5. **Held-out test:** evaluate on a region or date not used in training. Double-bounce strength depends on crop stage, planting density and water depth, so a model that only works on its training area has not solved the problem.
6. **Compare against the baseline, not against nothing.** Every model result is reported next to the Level 1 thresholding score on the same data.
7. **Test only on hand-made labels** (see Section 5, label quality warning).
8. **No leakage.** If a region or event (e.g. a Mekong event in Sen1Floods11) is used for training, it cannot also be in the held-out test set.
9. **Consistent pre-processing** between training and test data, or the pipeline-switch effect is measured separately.
10. **Targets come from your own results.** Do not borrow expected numbers from other people or other AI tools; X and Y come from Level 1 and Level 2.

### Pre-registration record

Keep a dated file (e.g. `evaluation_plan.md`) in the project repository containing the rules above plus the chosen X and Y. Commit it to version control before training. The commit date is your proof that the criteria came first.

---

## 7. Build order

Each level must produce a finished result before moving on. No level is skipped.

### Step 0 — Confirm data access

Before any technical work, check what validation data you can actually get.

| Check | Action |
| --- | --- |
| Sentinel-1 for Oct 2020 over Banteay Meanchey | Register on Copernicus Data Space, search, confirm scenes exist for before / during / after |
| Sentinel Asia products | Check whether downloadable flood polygons exist without membership; if unclear, email and ask |
| UNOSAT / HDX | Search for any Cambodia 2020 flood vector data |
| Sentinel-2 | Search for any low-cloud scene within a few days of a Sentinel-1 acquisition |
| JRC Global Surface Water | Confirm it covers the study area |
| Ready-processed radar (ARD) | Check which ready-processed Sentinel-1 sources are currently available (e.g. Microsoft Planetary Computer Sentinel-1 RTC, ASF on-demand RTC, Copernicus Data Space processing options) and whether they cover Oct 2020 over Banteay Meanchey |
| Pre-processing match | Find out how each benchmark dataset was processed; decide which pipeline will be used for everything |
| Label origins | For each benchmark, confirm which labels are hand-made and which are automatic, and how automatic ones were generated |
| Benchmark datasets | Confirm download works |

**Decision rule:**
- Tier F available → use it as an extra comparison
- Tier F not available → proceed with A + B + D; no change to the plan

**Deliverable:** a short written note listing what was obtained and what was not. The project proceeds either way.

---

### Level 0 — Practice on a solved dataset

Start where correct answers exist.

| Dataset | Type | Notes |
| --- | --- | --- |
| Sen1Floods11 | Radar + optical | Widely used starting point |
| Kuro Siwo | Radar only | Large |
| UrbanSARFloods | Radar (SLC) | Built for hard cases: urban and open-area flooding |

**Check early:**
- How many rice-paddy / flooded-vegetation examples do these datasets actually contain? If very few, that limits what the model can learn — and is itself worth noting.
- Which labels are hand-made and which are automatic (Section 5).
- Whether any event is in Southeast Asia / the Mekong — useful regional data, but it must not appear in both training and test sets.

**Deliverable:** you can load radar data and display it.

---

### Level 1 — Simple method, measured

No AI. Dark pixels = water, using histogram thresholding.

**Deliverable:** flood map + scores, **split by land-type stratum** (Section 5). This is the baseline.

---

### Level 2 — Failure analysis

Look at where thresholding fails and explain the physics.

| Failure | Cause |
| --- | --- |
| Terrain shadow read as water | Hills block radar, creating dark areas |
| Smooth roads / airstrips read as water | Flat surfaces reflect away like water |
| **Flooded vegetation missed** | Double bounce makes it bright |
| Wind-roughened water missed | Rough surface scatters signal back |

Also examine: do flooded-vegetation pixels look different in VH than in VV? If there is no visible difference in any input channel, that is an early warning that ML may not help — record it.

**Record the conditions of each failure.** Double bounce only happens when rice stalks are upright and the water is calm:
- Young, sparse rice → water dominates → may look dark (detected as water)
- Wind-roughened water → double bounce weakens
- Tall, dense rice → strong double bounce → looks bright (missed)

Where possible, note crop stage (from planting season / crop calendar) and wind conditions for each scene. This turns "flooded rice fails" into "flooded rice fails under these specific conditions" — a much stronger finding.

**Deliverable:** written analysis with example images per failure type. Then set X and Y (Section 6) and freeze the evaluation plan.

---

### Level 3 — Machine learning (hypothesis test)

**Framework:** PyTorch
**Approach:** semantic segmentation (classify every pixel)

**Model progression:**
1. U-Net from scratch — baseline
2. U-Net with pretrained backbone (e.g. ResNet)
3. Only later, transformer-based segmentation

**Input experiments:**
- VV only
- VV + VH (dual-pol — VH is more sensitive to vegetation structure)
- VV + VH + terrain (to suppress shadow false positives)

**Loss function experiments** (compare, don't assume):
- Weighted cross-entropy
- Dice loss
- Focal loss
- Dice + cross-entropy combined

**Important:** the labels only say flood / not flood. Flooded rice is not its own class, so these losses help with flood vs dry imbalance but do nothing specific for rice. To make training target the hypothesis directly, test **cropland-weighted loss**: use ESA WorldCover to give extra weight to flood pixels that fall on cropland.

**Training data:** hand-made labels first. If weak labels are added, report results for both (Section 5).

**Augmentation:** flips and rotations are common, but radar is side-looking — shadow and layover directions are tied to the satellite's viewing direction. Rotations may create physically unrealistic images. Test with and without.

**Compute:** start on the local RTX 3050 with small tiles (e.g. 256×256), small batch sizes and mixed precision. Move to free Kaggle / Colab GPUs only if memory runs out. Do not pay for compute at this stage.

**Deliverable:** results against the frozen evaluation plan, and a clear statement of which outcome occurred: confirmed, partial, or rejected.

---

### Level 4 — Apply to Cambodia

1. Download Sentinel-1 over Banteay Meanchey, before / during / after
2. Use the **same pre-processing pipeline chosen in Step 0** — preferably ready-processed (ARD) data rather than raw processing. If the pipeline differs from training data, measure the effect of the switch first (Section 5)
3. Run Level 1 and Level 3 methods
4. Validate using the ladder:
   - Tier B hand labels (primary)
   - Tier D to exclude permanent water
   - Tier C if a clear optical scene exists
   - Tier E sanity check
   - Tier F if obtained

**Deliverable:** a flood map of a real Cambodian disaster, scored against Cambodia-specific labels, with results split by land type.

---

### Level 5 — Change detection over time

Separate new flooding from normal seasonal water. Essential in Cambodia: Tonle Sap expands dramatically every year as a normal event. Use JRC Global Surface Water plus pre-event radar as the reference.

**Deliverable:** flood extent that excludes permanent and normal seasonal water.

---

### Level 6 — Pipeline

Automate: find new data → download → preprocess → run model → store result.

**Deliverable:** runs without manual steps.

---

### Level 7 — Intelligence output

A decision-useful report instead of a picture.

```
Flood Event — Banteay Meanchey
Detected:            14 Oct 2020
Flooded area:        XXX km²
  of which cropland: XX km²
Change since last pass: +XX km²
Method:              Sentinel-1 VV+VH, U-Net
Known limitation:    flooded-vegetation recall XX% (validated on hand labels)
```

Note the "known limitation" line. Stating the model's weakness in its own output is what makes it trustworthy.

**Deliverable:** a report a non-technical person could act on.

---

## 8. Technology stack

Only add a tool when a real problem forces it.

| Layer | Choice | Notes |
| --- | --- | --- |
| Language | Python | Already known |
| ML | PyTorch | Already known |
| Raster processing | rasterio, GDAL | Standard for satellite data |
| Vector / geometry | GeoPandas, Shapely | Map shapes |
| Data discovery | STAC | Standard satellite catalogue format |
| Radar data | Copernicus Data Space | Free Sentinel-1 (raw) |
| Ready-processed radar | Planetary Computer RTC / ASF RTC / CDSE processing | Avoids error-prone raw processing — confirm availability in Step 0 |
| Tile loading | torchgeo (+ rasterio) | Loads satellite tiles into PyTorch without running out of memory |
| Compute | Local RTX 3050; Kaggle / Colab free tier as backup | Paid compute not needed yet |
| Land cover | ESA WorldCover | For land-type stratification |
| Water reference | JRC Global Surface Water | Permanent / seasonal water |
| Labelling | QGIS | For Tier B hand labels |
| Storage | Plain disk folders | Sufficient at this scale |
| Database | PostgreSQL + PostGIS | Add at Level 6 |
| API | FastAPI | Add at Level 6 |
| Frontend | Next.js + MapLibre | Add at Level 7 |

### Explicitly deferred

These solve "too much data, too slow." That problem does not exist yet.

| Tool | What it is | When to add |
| --- | --- | --- |
| Object storage | File storage for programs | When disk is genuinely insufficient |
| MinIO | Makes your computer act like cloud storage | When deploying to cloud |
| Workers | Multiple program copies running in parallel | When processing is genuinely too slow |
| Dask | Splits huge data across workers | When data exceeds memory |

---

## 9. Concepts to learn

### Radar fundamentals
- Backscatter
- Why water appears dark
- VV vs VH polarisation
- Double bounce and why it inverts the signal
- Speckle and filtering

### Preprocessing
- Orbit correction, radiometric calibration, terrain correction, dB conversion
- Sigma-nought vs gamma-nought, and why mixing them breaks a model
- Speckle filters (Lee, Refined Lee) and their trade-offs

### Geospatial basics
- Coordinate reference systems, raster vs vector, GeoTIFF

### Evaluation and research method
- IoU, precision, recall
- Why overall accuracy misleads on imbalanced data
- Stratified evaluation (scores per land type)
- Held-out testing and why models overfit to local conditions
- Pre-registration: fixing criteria before seeing results
- Labelling protocols and inter-annotator agreement
- Label noise: how automatically generated labels can carry a method's bias into a model
- Data leakage between training and test sets

---

## 10. Risks

| Risk | Mitigation |
| --- | --- |
| Official maps not obtainable | Validation ladder — project does not depend on them |
| Benchmark datasets contain few flooded-rice examples | Check in Level 0; hand-label Cambodian examples (Tier B) |
| Hand labels are only as good as the labeller | Written protocol, "uncertain" class, second labeller on a subset |
| No cloud-free optical scene near the event | Tier C is optional by design |
| U-Net does not solve flooded rice | Allowed outcome; Level 2 analysis explains it |
| Temptation to change metrics after seeing results | Evaluation plan committed to version control before training |
| Model works only on training region | Held-out region/date test is mandatory |
| Radar preprocessing is error-prone | Use ready-processed (ARD) radar wherever possible |
| Training and Cambodia data processed differently | One pipeline for everything, or measure the switch effect separately |
| Weak labels carry the "dark = water" bias | Test only on hand-made labels; compare hand-only vs weak-label training |
| Same event in training and test set (leakage) | Split by event/region, not by random tile |
| Speckle filtering erases small flooded paddies | Apply filtering consistently; test with and without |
| Loss function helps flood vs dry but not rice | Test cropland-weighted loss |
| Borrowing expected numbers from others | Targets set only from own Level 1–2 results |
| Laptop GPU runs out of memory | Small tiles, small batches, mixed precision; free Kaggle / Colab as backup |
| Building the platform too early | Levels strictly ordered |

---

## 11. What "done" looks like

| Stage | Done means |
| --- | --- |
| Step 0 | Written note of what data is and isn't obtainable |
| Level 0 | Can load and view radar data; know how many rice examples exist |
| Level 1 | Baseline scores, split by land type |
| Level 2 | Failure analysis written; evaluation plan frozen and committed |
| Level 3 | Results reported against the frozen plan; outcome stated honestly |
| Level 4 | Validated flood map of a real Cambodian flood |
| Level 5 | Real flooding separated from seasonal water |
| Level 6 | Runs automatically |
| Level 7 | Usable report that states its own limitations |

**Step 0 through Level 4 is a complete, defensible project on its own** — regardless of which hypothesis outcome occurs. **Levels 5–7 are stretch goals** — essentially a separate software engineering project. If time runs out, a finished Level 4 with a strong written analysis is a success.

---

## 12. Immediate next steps

1. **Step 0:** register on Copernicus Data Space and confirm Sentinel-1 scenes exist for October 2020 over Banteay Meanchey
2. **Step 0:** check Sentinel Asia / HDX for downloadable flood polygons; email if unclear
3. Download Sen1Floods11: count flooded-vegetation examples, confirm which labels are hand-made vs automatic, and check how it was pre-processed
4. **Step 0:** choose one pre-processing pipeline (preferably ready-processed ARD) for all data
5. Read one paper on SAR flood mapping in vegetated areas to see what has already been tried

---

## Appendix A — Key reference points

- **Anchor event:** Cambodia floods, October 2020
- **Target province:** Banteay Meanchey
- **Radar data:** Sentinel-1, Copernicus Data Space
- **Guaranteed validation:** benchmark datasets, own hand labels, JRC Global Surface Water
- **Optional validation:** Sentinel Asia (access unconfirmed), cloud-free Sentinel-2
- **Land-type stratification:** ESA WorldCover
- **Target limitation:** radar underestimation of standing water in vegetated areas (documented by UNOSAT)
- **Benchmarks:** Sen1Floods11, Kuro Siwo, UrbanSARFloods

## Appendix B — Changes from version 1

- Added **Step 0**: confirm data access before technical work
- Added **Section 5**: validation ladder — project no longer depends on Sentinel Asia products
- Added land-type stratification (ESA WorldCover) so flooded-rice performance is measurable
- Added **Section 6**: hypothesis stated explicitly, three allowed outcomes, pre-registered evaluation rules
- Level 3 reframed as a hypothesis test rather than an assumed fix
- Level 2 now ends by freezing the evaluation plan
- Held-out region/date testing made mandatory
- Risks updated accordingly

## Appendix C — Changes from version 2

- Recommended ready-processed (ARD) radar instead of raw processing; availability checked in Step 0
- Added **label quality warning**: some benchmark labels were made with "dark = water" thresholding; testing only on hand-made labels
- Added **pre-processing consistency** rules: training and Cambodia data must be processed the same way, or the switch effect measured
- Added pre-registered rules 7–10 (hand-made test labels, no leakage, consistent processing, own targets)
- Level 2 now records crop stage and wind conditions for each failure
- Level 3: loss function treated as an experiment; added cropland-weighted loss to target rice directly; augmentation caution for side-looking radar; local GPU first
- Added torchgeo and ARD sources to the tech stack
- Levels 5–7 explicitly marked as stretch goals
- Risks updated with new items