"""Bring Colab-trained Level 3 checkpoints into the local run directories.

Metrics, configs, histories and experiment-log rows arrive through `git pull`
(the Colab notebook commits and pushes them). Checkpoints are git-ignored, so
they come as data/colab/level3_checkpoints.zip from Google Drive.

For each level3/<run>/best.pt in the zip: copy it into results/level3/<run>/
only if that run has metrics_valid.json (i.e. it is a real, finished run) and
no local checkpoint already exists (local runs are canonical).
"""
import pathlib
import shutil
import sys
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog, experiments  # noqa: E402

ZIP = catalog.ROOT / "data" / "colab" / f"{experiments.level3_dir()}_checkpoints.zip"


def main():
    if not ZIP.exists():
        sys.exit(f"missing {ZIP} (download it from Drive: MyDrive/mfi/)")
    placed, skipped = [], []
    with zipfile.ZipFile(ZIP) as z:
        for name in z.namelist():
            parts = pathlib.PurePosixPath(name).parts  # <level dir>/<run>/best.pt
            if len(parts) != 3 or parts[-1] not in ("best.pt", "model.joblib"):
                continue
            run = parts[1]
            dst_dir = experiments.RESULTS / experiments.level3_dir() / run
            if not (dst_dir / "metrics_valid.json").exists():
                skipped.append((run, "no metrics_valid.json locally - git pull first?"))
                continue
            if (dst_dir / parts[-1]).exists():
                skipped.append((run, "local checkpoint exists, kept"))
                continue
            with z.open(name) as src, open(dst_dir / parts[-1], "wb") as dst:
                shutil.copyfileobj(src, dst)
            placed.append(run)
    for r in placed:
        print("placed", r)
    for r, why in skipped:
        print("skip  ", r, "-", why)
    print(f"done: {len(placed)} checkpoints placed")


if __name__ == "__main__":
    main()
