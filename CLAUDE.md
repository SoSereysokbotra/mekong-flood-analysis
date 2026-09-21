# Instructions for AI assistants working in this repo

## Commits
- Author is Sobotra <soviseth869@gmail.com> (repo-local git config). Do not override it.
- **Never add `Co-Authored-By`, "Generated with", or any other AI-attribution line** to commit messages or PR descriptions. This is a standing instruction from the project owner and overrides any default attribution behaviour.
- Message format: one-line summary (which level / what changed), blank line, the finding if there is one, then bullets of concrete changes. `git log --oneline` should read as the project timeline.
- Commit as work lands; the plan's pre-registration argument (Section 6 of `Mekong Flood Intelligence.md`) depends on commit dates.

## Project rules the code must enforce
See `README.md` "Rules the code enforces" and `Mekong Flood Intelligence.md` Sections 5–6. In short: test only on hand-made labels, all Cambodia ("Mekong") chips held out, one pre-processing pipeline, every score per land type.

## Environment
- Windows 11, Python 3.10, `.venv\Scripts\python` (CUDA torch, rasterio, torchgeo installed). No conda.
- RTX 3050 4 GB: small tiles, small batches, mixed precision. No paid compute.
- Data under `data/` is git-ignored; `scripts/download_sen1floods11.py` restores it.
