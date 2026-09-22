"""Merge Level 3 results trained on Colab into the local repo.

Expects data/colab/level3_colab_results.zip (made by notebooks/colab_level3.ipynb),
containing experiment_log.csv and results/level3/<run>/ directories.

- Copies each run directory that does not already exist locally (never
  overwrites a local run: local runs were trained here and are canonical).
- Appends experiment-log rows from Colab that are not already present
  (keyed on timestamp + level + run_id + split), tagging the note with
  "trained on Colab".
"""
import csv
import pathlib
import shutil
import sys
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog, experiments  # noqa: E402

ZIP = catalog.ROOT / "data" / "colab" / "level3_colab_results.zip"
TMP = catalog.ROOT / "data" / "colab" / "_merge"


def main():
    if not ZIP.exists():
        sys.exit(f"missing {ZIP}")
    if TMP.exists():
        shutil.rmtree(TMP)
    with zipfile.ZipFile(ZIP) as z:
        z.extractall(TMP)
    src_level3 = TMP / "level3"
    copied = []
    for d in sorted(src_level3.iterdir()):
        if not d.is_dir() or d.name.startswith("_") or not (d / "metrics_valid.json").exists():
            continue
        dst = experiments.RESULTS / "level3" / d.name
        if dst.exists() and (dst / "metrics_valid.json").exists():
            print(f"keep local {d.name}")
            continue
        shutil.copytree(d, dst, dirs_exist_ok=True)
        copied.append(d.name)
        print(f"copied {d.name}")
    for log in (src_level3 / "_logs").glob("*.log") if (src_level3 / "_logs").exists() else []:
        shutil.copy(log, experiments.RESULTS / "level3" / "_logs" / log.name)

    local = experiments.read_log()
    seen = {(r["timestamp"], r["level"], r["run_id"], r["split"]) for r in local}
    with open(TMP / "experiment_log.csv", newline="") as f:
        remote = list(csv.DictReader(f))
    added = 0
    with open(experiments.LOG, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=experiments.LOG_FIELDS)
        for r in remote:
            key = (r["timestamp"], r["level"], r["run_id"], r["split"])
            if key in seen or r["run_id"] not in copied:
                continue
            r["note"] = (r.get("note", "") + "; trained on Colab").strip("; ")
            w.writerow({k: r.get(k, "") for k in experiments.LOG_FIELDS})
            added += 1
    shutil.rmtree(TMP)
    print(f"done: {len(copied)} runs copied, {added} log rows appended")


if __name__ == "__main__":
    main()
