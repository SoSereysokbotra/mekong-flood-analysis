1. Results written into markdown by hand instead of saved as artefacts (CSV / JSON / predictions) that figures are generated from.
2. Several docs drifting to different numbers — no single experiment log.
3. Choosing a model, threshold or loss by looking at the held-out test (Mekong) scores.
4. Discovering a train/valid overlap (same event, same scene) after results are published.
5. Building the platform (Levels 5–7: PostGIS, FastAPI, Next.js) before the science (Level 4) is finished.
6. Stating a conclusion ("U-Net recovers flooded rice") from a pooled score, not from a per-stratum measurement.
7. Hand labels made without a written protocol, labeller, date, and "uncertain" class.
8. Not measuring the key assumption *before* investing — here: whether bright double-bounce rice exists in the Sen1Floods11 labels at all.