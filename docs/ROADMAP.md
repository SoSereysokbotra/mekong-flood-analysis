# Roadmap: from research project to production system

Written 6 Nov 2026. Work through it over several days. Tick each box (`[x]`) and commit as you go,
so this file always shows where we stopped.

**Goal:** turn the flood check into a system that is **reliable** (tested), **maintainable**
(clean code), **good quality** (the model is monitored) and **scalable** (all of Cambodia,
every 6 days, without anyone running it by hand).

**Rule for every phase:** the 14 Oct 2020 Banteay Meanchey numbers must not change
(882 / 1,131 / 1,218 km² for threshold / VV-only U-Net / selected model; source:
`results/level4/`, `docs/level4_cambodia.md`). If a change moves them, the change is wrong.

**Review rule (the user's instruction, 6 Nov 2026):** Gemini is the reviewer for this roadmap.
When Claude finishes **each task** (each checkbox), Claude ends its message with a
**ready-to-paste prompt for Gemini**. The user pastes it into Gemini and brings the answer back.
Claude checks each Gemini finding on merit: fix it if it is right, explain if it is wrong.
A task is ticked `[x]` only after the Gemini review is resolved.

### Gemini prompt template

Claude fills in the `<...>` parts. The prompt must name exact files and commits, so Gemini can
read them on GitHub (https://github.com/SoSereysokbotra/mekong-flood-analysis); push first.

```
You are reviewing one task in my project "Mekong Flood Intelligence"
(Sentinel-1 radar flood detection for Cambodia).
Repo: https://github.com/SoSereysokbotra/mekong-flood-analysis  — commit <hash>

Task: <roadmap phase and checkbox text>
What was changed: <files changed, one line each>
What it is supposed to do: <expected behaviour>
How it was checked: <tests run, their output, numbers compared>

Please check:
1. Is the change correct? Look for bugs, wrong logic, edge cases.
2. Does it break any project rule? (test only on hand labels; Cambodia/Mekong chips held out;
   every number comes from a results file; the 14 Oct 2020 numbers 882 / 1,131 / 1,218 km²
   must not change)
3. <task-specific question>
4. Anything missing that this task should have done?

For each problem: file, line, what is wrong, how to fix. Say "no problems found" if none.
```

---

## Where we start (checked 6 Nov 2026)

| What | State |
| --- | --- |
| Tests | none (no `tests/` folder) |
| Automatic checks on each push (CI) | none (no `.github/workflows/`) |
| Code layout | ~5,800 lines in `scripts/`, only ~1,300 in the library `src/mfi/` |
| Library versions | not pinned (only `numpy<2`); an update could change results |
| Model | zip file in Google Drive, run by hand on Colab |
| Provinces | `check_flood.py --province X` works, **one province at a time, by hand** |
| Accuracy | measured in **Banteay Meanchey only** |

## Phase 0: close the open task (do this first, ~10 min)

- [x] Run `.venv\Scripts\python scripts/tierb2026.py status` for the September 2026 flood labels.
  The deadline in `data/labels/LABELLING_PROTOCOL.md` §9 was **31 Oct 2026**.
  - A date qualified → follow HANDOFF §2b (prepare → review → apply → score).
  - No date qualified → record "no usable optical" in the protocol log and close it. Do not loosen the rule.
  - **Result (6 Nov 2026): a date qualified.** Optical 4 Oct 2026 (17 of 20 tiles clear), radar 2 Oct 2026.
- [x] `prepare`: 66 water candidates + 34 cloud areas → `data/labels/tierB_bmc_sep2026.gpkg`, review page built.
- [x] Sobotra reviews `data/labels/2026/review.html`: 34 water, 16 not, 16 unsure.
- [x] Flood check for radar date 2 Oct 2026 on Colab → `results/check/2026-10-02/` (NORMAL FOR THE SEASON, 1.3×).
- [x] `apply` → `score` → `docs/level4_tierb2026_scores.md`. Ranking holds (cropland IoU 0.529 vs 0.496),
  but precision fell for all methods (~0.54 vs ~0.85 in 2020); cause not separable.
- [x] Gemini review of Phase 0 (6 Nov 2026). Accepted: tile-set bug in `score()` (fixed), doc tile counts,
  "dry = never reviewed" made prominent, protocol §5 sensitivity run added, this box. Headline unchanged.
- [x] 2020 scorer re-checked (user chose to fix it): BMC_CROP_18's saved 2020 scene is 98 % no data, so it was
  rightly excluded. Both scorers share `tiles_to_score()`; 2020 and 2026 scores identical after the change.

## Phase 1: reliability, prove it works (~1 week)

- [x] Create `tests/` and add `pytest` to the dev setup (`[tool.pytest.ini_options]` in `pyproject.toml`).
- [x] Unit tests for `src/mfi/metrics.py` (`tests/test_metrics.py`, 8 tests).
- [x] Unit tests for `src/mfi/strata.py` and `src/mfi/threshold.py` (`test_strata.py`, `test_threshold.py`).
- [x] **Golden test** (`tests/test_golden_2020.py`, marked `slow`): re-runs the three methods on the cached
  26 Sep / 14 Oct 2020 radar and matches `results/level4/change_detection.json` (882 / 1,131 / 1,218 km²)
  to 0.1 km². Passes locally (8 Nov 2026); skips itself where the cache or checkpoints are missing.
- [x] Split tests (`test_split.py`): rule on a fake list, plus real data (no Mekong outside test; sizes
  301 / 48 / 30 under v1.1, Paraguay has no RTC).
- [x] Tier B tile rule moved to `src/mfi/tierb.py` and tested (`test_tierb.py`).
- [x] `ruff` added with project settings; 198 findings fixed or checked. 7 × B023 checked by hand
  (closures called in the same loop pass, harmless) and allowed per file. Long lines (E501) left for Phase 2.
- [x] GitHub Actions `.github/workflows/ci.yml`: ruff + fast tests on every push, without PyTorch.
- [ ] Gemini review of Phase 1.

## Phase 2: maintainability, clean structure (~1–2 weeks)

- [ ] Move the logic out of `scripts/check_flood.py` into the library (e.g. `src/mfi/check.py`);
  the script becomes a few lines that call it.
- [ ] Same for the Level 7 report (`scripts/level7_report.py`, `level7_district_areas.py`).
- [ ] One command-line tool: `mfi check --date ... --province ...` (entry point in `pyproject.toml`).
- [ ] Move settings into `configs/` (thresholds, tracks, provinces, file paths), not hard-coded.
- [ ] Pin library versions in a lock file (`uv lock` or `pip-tools`).
- [ ] Type hints + docstrings on public functions.
- [ ] Delete or move the untracked `scratch_check_*.py` files (re-checks from the Gemini audit).

## Phase 3: quality, watch the model

- [ ] Give each model a version (e.g. `unet_vvvh_cropw@v1.1`) and write it into every report and map.
- [ ] Input checks on every new radar image: brightness in the normal range, province fully covered
  (`MIN_COVERAGE` in `check_flood.py`), which satellite it came from.
- [ ] **S1C / S1D were never tested against labels.** Compare their brightness with S1A on the same
  places; flag reports made from them until this is done.
- [ ] Re-score the model whenever new labels exist (like the 2026 task in Phase 0).

## Phase 4: scalability, all of Cambodia, automatic

Each radar pass is ~350 MB and each check needs 2 dates × 4 years, so **none of this can run on
the home connection** (~100 KB/s). It must run on Colab or in the cloud.

- [ ] `--province all`: run every province. Better: process **per radar pass** (one pass covers
  several provinces; download once, cut into provinces).
- [ ] Run provinces in parallel; write one national table (`results/check/<date>/cambodia.csv`)
  and one national map.
- [ ] Package in Docker so it runs the same on Colab, laptop or server.
- [ ] Schedule it every 6 days (Sentinel-1 repeat on track 164): GitHub Actions cron or a cloud job.
- [ ] Alert (email or Telegram) when any province reports **UNUSUAL FLOODING**.
- [ ] Optional: simple web map of the latest result.

## Phase 5: make accuracy scale too

Scaling the **code** is easy; scaling the **accuracy claim** is not. Until this phase is done,
other provinces' numbers must be described as "the model says X km²", not "X km² with tested accuracy".

- [ ] Choose 2–3 provinces with different landscapes:
  - one around the **Tonle Sap** (lots of normal seasonal water),
  - one **hilly** province in the north or east (slopes cast radar shadow that looks like water),
  - one on the **Mekong river** floodplain.
- [ ] Hand labels there with the same protocol and review page (`scripts/make_review_page.py`).
- [ ] Score per province and per land type; write which provinces the model is trusted in.
- [ ] Hilly provinces: consider a terrain/slope mask (DEM) before trusting their numbers.

---

## Notes for whoever picks this up

- Read `HANDOFF.md` first; its rules still apply (no test peeking, numbers come from artefacts,
  no AI attribution in commits).
- Do the phases in order: tests before refactoring, so a refactor cannot silently change results.
- The user decides when to start each phase. Ask, do not assume.
- After every finished task: push, then give the Gemini review prompt (template at the top).
