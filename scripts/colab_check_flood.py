"""Run scripts/check_flood.py on Colab and keep the result on Drive.

Each radar pass is ~250-500 MB; a check with three comparison years reads
eight. On Colab that is minutes, on a slow home connection it is hours.

Steps:
  1. unzip the Level 3 v1.1 checkpoints from Drive (same as colab_level4.py)
  2. run scripts/check_flood.py with the arguments given here
  3. copy the result folder to MyDrive/mfi/check/...

Usage in Colab (after cloning the repo and mounting Drive):
    !python scripts/colab_check_flood.py --province Battambang --date 2026-09-28
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
    p = subprocess.Popen([sys.executable, "scripts/check_flood.py", *sys.argv[1:]],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    result = None
    for line in p.stdout:                      # pass the output through as it comes
        print(line, end="", flush=True)
        if line.startswith("RESULT_DIR="):
            result = pathlib.Path(line.split("=", 1)[1].strip())
    if p.wait() != 0 or result is None:
        sys.exit("check_flood.py failed")
    if DRIVE.is_dir():
        dst = DRIVE / "check" / result.relative_to(experiments.RESULTS / "check")
        shutil.copytree(result, dst, dirs_exist_ok=True)
        print(f"saved to Drive: {dst}")


if __name__ == "__main__":
    main()
