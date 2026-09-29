"""Run scripts/check_flood.py on Colab and keep the result on Drive.

Each radar pass is ~350 MB; a check with three comparison years reads eight.
On Colab that is minutes, on a slow home connection it is hours.

Steps:
  1. unzip the Level 3 v1.1 checkpoints from Drive (same as colab_level4.py)
  2. run scripts/check_flood.py with the arguments given here
  3. copy results/check/<date>/ to MyDrive/mfi/check/<date>/

Usage in Colab (after cloning the repo and mounting Drive):
    !python scripts/colab_check_flood.py --date 2026-10-15
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog, experiments  # noqa: E402
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from colab_level4 import DRIVE, ensure_checkpoints  # noqa: E402


def main():
    os.chdir(catalog.ROOT)
    ensure_checkpoints()
    before = {p.name for p in (experiments.RESULTS / "check").glob("*")}
    r = subprocess.run([sys.executable, "scripts/check_flood.py", *sys.argv[1:]])
    if r.returncode != 0:
        sys.exit("check_flood.py failed")
    new = sorted({p.name for p in (experiments.RESULTS / "check").glob("*")} - before) or \
        sorted(p.name for p in (experiments.RESULTS / "check").glob("*"))[-1:]
    for name in new:
        src = experiments.RESULTS / "check" / name
        if DRIVE.is_dir():
            dst = DRIVE / "check" / name
            shutil.copytree(src, dst, dirs_exist_ok=True)
            print(f"saved to Drive: {dst}")
        print(f"RESULT_DIR={src}")


if __name__ == "__main__":
    main()
