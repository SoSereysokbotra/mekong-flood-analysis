"""Run Level 4 (Cambodia inference) on Colab.

Reading the October 2020 scenes over the whole province is ~700 MB at 20 m.
On a home connection to Azure blob that is hours; on Colab it is minutes, and
the T4 runs the U-Nets faster too. Everything else is identical to running
scripts/level4_cambodia.py locally.

Steps:
  1. unzip the Level 3 v1.1 checkpoints from Drive (MyDrive/mfi/level3_rtc_checkpoints.zip)
  2. run scripts/level4_cambodia.py
  3. push areas.csv / areas.json to GitHub, zip the flood maps to Drive

Usage in Colab (after cloning the repo and mounting Drive):
    import os
    from google.colab import userdata
    os.environ['GITHUB_TOKEN'] = userdata.get('GITHUB_TOKEN')
    !python scripts/colab_level4.py
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog, experiments  # noqa: E402

DRIVE = pathlib.Path("/content/drive/MyDrive/mfi")
CKPT_ZIP = DRIVE / "level3_rtc_checkpoints.zip"


def sh(cmd: str, check: bool = True, secret: str | None = None) -> int:
    # never echo a credential: the remote URL carries the GitHub token
    shown = cmd.replace(secret, "***") if secret else cmd
    print(f"$ {shown}", flush=True)
    r = subprocess.run(cmd, shell=True)
    if check and r.returncode != 0:
        sys.exit(f"failed: {cmd}")
    return r.returncode


def ensure_checkpoints():
    need = ["unet_vv_ce", "unet_vvvh_cropw"]
    missing = [r for r in need if not (experiments.RESULTS / "level3_rtc" / r / "best.pt").exists()]
    if not missing:
        print("checkpoints present")
        return
    if not CKPT_ZIP.exists():
        have = sorted(p.name for p in DRIVE.glob("*")) if DRIVE.is_dir() else "(MyDrive/mfi does not exist)"
        sys.exit(f"STOP: {CKPT_ZIP} not found. Drive folder contains: {have}")
    sh(f"cd '{experiments.RESULTS}' && unzip -o -q '{CKPT_ZIP}'")
    still = [r for r in need if not (experiments.RESULTS / "level3_rtc" / r / "best.pt").exists()]
    if still:
        sys.exit(f"STOP: checkpoints still missing after unzip: {still}")
    print(f"unzipped checkpoints for {need}")


def push():
    tok = os.environ.get("GITHUB_TOKEN")
    if not tok:
        print("no GITHUB_TOKEN in the environment - skipping push.")
        print("In a notebook cell: os.environ['GITHUB_TOKEN'] = userdata.get('GITHUB_TOKEN')")
        return
    repo = "github.com/SoSereysokbotra/mekong-flood-analysis.git"
    sh("git config user.name 'Sobotra'")
    sh("git config user.email 'soviseth869@gmail.com'")
    sh(f"git remote set-url origin https://x-access-token:{tok}@{repo}", secret=tok)
    sh("git stash --quiet --include-untracked", check=False)
    sh("git pull --rebase --quiet origin main", check=False)
    sh("git stash pop --quiet", check=False)
    sh("git add results/level4")
    msg = ("Level 4: seasonal baseline across normal years 2018-2022 (Colab)"
           if "--normal-years" in sys.argv
           else "Level 4: Banteay Meanchey flood areas, Oct 2020 (Colab)\n\n"
                "Three models on RTC track 164 (26 Sep / 14 Oct / 1 Nov 2020), "
                "areas split by land type and by JRC permanent water.")
    subprocess.run(["git", "commit", "-q", "-m", msg])
    sh("git push --quiet origin main", check=False)
    sh(f"git remote set-url origin https://{repo}")
    sh("git log --oneline | head -1", check=False)
    if DRIVE.is_dir():
        zip_path = DRIVE / "level4_maps.zip"
        sh(f"cd '{experiments.RESULTS}/level4' && zip -q -r '{zip_path}' maps", check=False)
        sh(f"ls -la '{zip_path}'", check=False)
        print(f"\nLocally: git pull, then download {zip_path.name} to data/colab/ if you want the rasters.")


def main():
    """--normal-years runs the seasonal baseline instead of the event dates."""
    os.chdir(catalog.ROOT)
    ensure_checkpoints()
    script = "scripts/level4_normal_years.py" if "--normal-years" in sys.argv else "scripts/level4_cambodia.py"
    r = subprocess.run([sys.executable, script])
    if r.returncode != 0:
        sys.exit(f"{script} failed")
    push()


if __name__ == "__main__":
    main()
