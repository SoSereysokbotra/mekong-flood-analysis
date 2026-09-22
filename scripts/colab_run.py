"""One entry point for a Colab run, so the notebook stays a two-line launcher
and can never go stale: all logic lives here, in the repo, and the repo is
pulled fresh every time.

Steps:
  1. unzip the chip cache for the active pipeline from Drive (if not already there)
  2. run the per-pixel controls, then every configs/level3/*.yaml not yet done
  3. commit + push metrics to GitHub, zip checkpoints to Drive

Test is never scored here (that is scripts/level3_test.py, run locally after
a selection is recorded).

Usage in Colab:
    !python scripts/colab_run.py
    !python scripts/colab_run.py --no-push      # train only
"""
from __future__ import annotations

import argparse
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog, experiments  # noqa: E402

DRIVE = pathlib.Path("/content/drive/MyDrive/mfi")
ORDER = ["unet_vvvh_ce", "unet_vv_ce", "unet_vvvh_cropw", "unet_vvvh_dice_ce",
         "unet_vvvh_focal", "unet_vvvh_slope", "unet_vvvh_noaug", "unet_r18_vvvh"]


def sh(cmd: str, check: bool = True) -> int:
    print(f"$ {cmd}", flush=True)
    r = subprocess.run(cmd, shell=True)
    if check and r.returncode != 0:
        sys.exit(f"failed: {cmd}")
    return r.returncode


def prepare_cache() -> pathlib.Path:
    """Unzip the chip cache for the active pipeline; return its directory."""
    from mfi import data

    cache = data.CACHE
    name = cache.name  # chip_cache_rtc or chip_cache
    zip_path = DRIVE / f"{name}.zip"
    if cache.is_dir() and any(cache.glob("*.npz")):
        print(f"cache present: {cache} ({len(list(cache.glob('*.npz')))} chips)")
        return cache
    if not zip_path.exists():
        have = sorted(p.name for p in DRIVE.glob("*")) if DRIVE.is_dir() else "(MyDrive/mfi does not exist)"
        sys.exit(f"STOP: {zip_path} not found. Drive folder contains: {have}\n"
                 f"Upload data/colab/{name}.zip to Google Drive at MyDrive/mfi/ and re-run.")
    cache.parent.mkdir(parents=True, exist_ok=True)
    sh(f"unzip -q '{zip_path}' -d /tmp/cc")
    sh(f"mv /tmp/cc/{name} '{cache}'")
    norm_dir = experiments.RESULTS / experiments.level3_dir()
    norm_dir.mkdir(parents=True, exist_ok=True)
    sh(f"cp /tmp/cc/_norm_stats.json '{norm_dir / '_norm_stats.json'}'", check=False)
    print(f"unzipped {len(list(cache.glob('*.npz')))} chips to {cache}")
    return cache


def train_all(level_dir: str):
    logs = experiments.RESULTS / level_dir / "_logs"
    logs.mkdir(parents=True, exist_ok=True)

    if not (experiments.RESULTS / level_dir / "pixel_logreg" / "metrics_valid.json").exists():
        print("=== per-pixel controls", flush=True)
        r = subprocess.run([sys.executable, "scripts/level3_pixel_control.py"], capture_output=True, text=True)
        print((r.stdout or "")[-1500:] or (r.stderr or "")[-1500:], flush=True)
        if r.returncode != 0:
            sys.exit("per-pixel controls failed")

    for cfg in ORDER:
        if (experiments.RESULTS / level_dir / cfg / "metrics_valid.json").exists():
            print(f"skip {cfg} (done)", flush=True)
            continue
        print(f"=== training {cfg}", flush=True)
        log = logs / f"{cfg}.log"
        with open(log, "w") as f:
            r = subprocess.run([sys.executable, "scripts/level3_train.py", f"configs/level3/{cfg}.yaml"],
                               stdout=f, stderr=subprocess.STDOUT)
        sh(f"grep -E '^ep |best epoch|Error|Traceback' '{log}' | tail -4", check=False)
        if r.returncode != 0:
            sys.exit(f"STOP: {cfg} failed - see {log}")
    print("ALL TRAINING DONE", flush=True)


def push(level_dir: str):
    # google.colab.userdata only works inside the notebook kernel, not in a
    # subprocess, so the launcher cell exports the token to the environment.
    tok = os.environ.get("GITHUB_TOKEN")
    if not tok:
        try:
            from google.colab import userdata  # type: ignore

            tok = userdata.get("GITHUB_TOKEN")
        except Exception:  # noqa: BLE001
            tok = None
    if not tok:
        print("no GITHUB_TOKEN available - skipping push.
"
              "In the notebook cell (not a subprocess) do:
"
              "    from google.colab import userdata; import os
"
              "    os.environ['GITHUB_TOKEN'] = userdata.get('GITHUB_TOKEN')
"
              "then re-run this script.")
        return
    repo = "github.com/SoSereysokbotra/mekong-flood-analysis.git"
    sh("git config user.name 'Sobotra'")
    sh("git config user.email 'soviseth869@gmail.com'")
    sh(f"git remote set-url origin https://x-access-token:{tok}@{repo}")
    sh("git stash --quiet --include-untracked", check=False)   # local data files must not block the pull
    sh("git pull --rebase --quiet origin main", check=False)
    sh("git stash pop --quiet", check=False)
    sh(f"git add results/experiment_log.csv results/{level_dir}")
    msg = (f"Level 3 {experiments.plan_version()}: valid results from Colab T4\n\n"
           f"Trained with scripts/level3_train.py under evaluation_plan {experiments.plan_version()}; "
           f"same configs, splits, controls and selection rule. Test not scored.")
    subprocess.run(["git", "commit", "-q", "-m", msg])
    sh("git push --quiet origin main", check=False)
    sh(f"git remote set-url origin https://{repo}")
    sh("git log --oneline | head -1", check=False)

    if DRIVE.is_dir():
        zip_path = DRIVE / f"{level_dir}_checkpoints.zip"
        sh(f"cd results && zip -q '{zip_path}' {level_dir}/*/best.pt {level_dir}/*/model.joblib", check=False)
        sh(f"ls -la '{zip_path}'", check=False)
        print(f"\nLocally: git pull, download {zip_path.name} to data/colab/, then python scripts/merge_colab_results.py")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-push", action="store_true")
    a = ap.parse_args()
    os.chdir(catalog.ROOT)
    level_dir = experiments.level3_dir()
    print(f"plan {experiments.plan_version()}  ->  results/{level_dir}  (MFI_PIPELINE={os.environ.get('MFI_PIPELINE', 'rtc')})")
    prepare_cache()
    from mfi import data  # after the cache exists

    sp = data.splits()
    print("split:", {k: len(v) for k, v in sp.items()})
    train_all(level_dir)
    if not a.no_push:
        push(level_dir)


if __name__ == "__main__":
    main()
