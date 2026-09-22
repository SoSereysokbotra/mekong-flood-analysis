"""Level 3: train one configuration, evaluate on valid every epoch, keep the
best epoch by the frozen selection score, log it. Never touches test.

Guard: refuses to run unless the commit "Freeze evaluation plan v1" is in the
git history (evaluation_plan.md). Test scoring is scripts/level3_test.py.

Usage:
    python scripts/level3_train.py configs/level3/unet_vvvh_ce.yaml
    python scripts/level3_train.py configs/level3/*.yaml      # several, sequentially
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import time

import numpy as np
import torch
import yaml
from torch.utils.data import DataLoader
from tqdm import tqdm

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog, data, experiments, metrics, models  # noqa: E402

LEVEL = "level3"
FREEZE_MSG = "Freeze evaluation plan v1"
NORM_PATH = experiments.RESULTS / LEVEL / "_norm_stats.json"
# Section 5 of evaluation_plan.md (frozen v1.0)
VALID_PRECISION_FLOOR = 0.48


def assert_frozen():
    log = subprocess.check_output(["git", "log", "--format=%s"], cwd=catalog.ROOT, text=True)
    if FREEZE_MSG not in log:
        sys.exit(f"refusing to train: commit '{FREEZE_MSG}' not found in git history")


def selection_score(m: dict) -> tuple[float, float]:
    """(score, tie-break) per evaluation_plan.md section 5."""
    if not (m["cropland"]["precision"] >= VALID_PRECISION_FLOOR):
        return (-1.0, m["cropland"]["iou"])
    return (min(m["cropland_bright"]["recall"], m["vegetation_bright"]["recall"]), m["cropland"]["iou"])


@torch.no_grad()
def evaluate(model, chips, channels, norm, device, save_pred_dir: pathlib.Path | None = None):
    """Full-chip evaluation; returns (metrics dict, per-chip rows)."""
    import rasterio
    from mfi import io

    model.eval()
    ds = data.ChipDataset(chips, channels, norm, crop=None, augment=False)
    conf, rows = metrics.Confusion(), []
    for i in range(len(ds)):
        b = ds[i]
        x = b["x"].unsqueeze(0).to(device)
        with torch.autocast("cuda", dtype=torch.float16, enabled=device.type == "cuda"):
            logits = model(x)
        pred = (logits.argmax(1)[0] == 1).cpu().numpy()
        y = b["y"].numpy()
        label = np.where(y == data.IGNORE, -1, y).astype(np.int8)
        land, vh = b["land"].numpy(), b["vh"].numpy()
        c = metrics.Confusion().add(pred, label, land, vh=vh)
        conf.merge(c)
        cm = c.metrics()
        rows.append({"chip": b["chip"], "event": catalog.s1f11_event(b["chip"]),
                     **{f"{g}_{k}": cm[g][k] for g in ("all", "cropland", "cropland_bright", "vegetation_bright", "open_water") for k in ("iou", "recall", "precision", "n_pos")}})
        if save_pred_dir is not None:
            save_pred_dir.mkdir(parents=True, exist_ok=True)
            with rasterio.open(catalog.s1f11_paths(b["chip"])["label"]) as src:
                prof = src.profile
            prof.update(dtype="uint8", count=1, compress="deflate", nodata=None)
            with rasterio.open(save_pred_dir / f"{b['chip']}.tif", "w", **prof) as dst:
                dst.write(pred.astype(np.uint8), 1)
    return conf.metrics(), rows


def fmt(m):
    return (f"allIoU {m['all']['iou']:.3f} | crop IoU {m['cropland']['iou']:.3f} rec {m['cropland']['recall']:.3f} "
            f"prec {m['cropland']['precision']:.3f} | bright crop {m['cropland_bright']['recall']:.3f} "
            f"veg {m['vegetation_bright']['recall']:.3f} | dark {m['cropland_dark']['recall']:.3f}")


def train_one(cfg_path: pathlib.Path):
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)
    run_id = cfg_path.stem
    torch.manual_seed(cfg.get("seed", 0))
    np.random.seed(cfg.get("seed", 0))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    sp = data.splits()

    if not NORM_PATH.exists():
        NORM_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(NORM_PATH, "w") as f:
            json.dump(data.fit_norm_stats(sp["train"]), f, indent=2)
    norm = data.load_norm(NORM_PATH)

    channels = cfg["channels"]
    model = models.build_model(cfg["model"], len(channels), cfg.get("pretrained", False)).to(device)
    loss_fn = models.build_loss(cfg)
    opt = torch.optim.AdamW(model.parameters(), lr=float(cfg.get("lr", 1e-3)), weight_decay=float(cfg.get("wd", 1e-4)))
    epochs = int(cfg.get("epochs", 30))
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=float(cfg.get("lr", 1e-3)), total_steps=epochs * (len(sp["train"]) * int(cfg.get("crops_per_chip", 4)) // int(cfg.get("batch", 8)) + 1))
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    train_ds = data.ChipDataset(sp["train"], channels, norm, crop=int(cfg.get("crop", 256)),
                                augment=bool(cfg.get("augment", True)), crops_per_chip=int(cfg.get("crops_per_chip", 4)), seed=cfg.get("seed", 0))
    dl = DataLoader(train_ds, batch_size=int(cfg.get("batch", 8)), shuffle=True, num_workers=0, drop_last=True)

    run_dir = experiments.run_dir(LEVEL, run_id)
    experiments.save_config(LEVEL, run_id, {**cfg, "run_id": run_id, "norm_stats": norm, "n_params": sum(p.numel() for p in model.parameters()),
                                            "device": str(device), "train_chips": len(sp["train"]), "valid_chips": len(sp["valid"])})
    best, history = None, []
    t0 = time.time()
    for ep in range(epochs):
        model.train()
        tl, n = 0.0, 0
        for b in tqdm(dl, desc=f"{run_id} ep{ep + 1}/{epochs}", leave=False):
            x, y, land = b["x"].to(device), b["y"].to(device), b["land"].to(device)
            opt.zero_grad(set_to_none=True)
            with torch.autocast("cuda", dtype=torch.float16, enabled=device.type == "cuda"):
                logits = model(x)
            loss = loss_fn(logits.float(), y, land)
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(opt)
            scaler.update()
            sched.step()
            tl += loss.item() * x.shape[0]
            n += x.shape[0]
        mv, _ = evaluate(model, sp["valid"], channels, norm, device)
        sc = selection_score(mv)
        history.append({"epoch": ep + 1, "train_loss": tl / n, "valid_score": sc[0], "valid_tiebreak": sc[1],
                        **{f"valid_{g}_{k}": mv[g][k] for g in ("all", "cropland", "cropland_bright", "vegetation_bright", "cropland_dark") for k in ("iou", "recall", "precision")}})
        print(f"ep {ep + 1:2d} loss {tl / n:.4f} | valid {fmt(mv)} | score {sc[0]:.3f} ({(time.time() - t0) / 60:.1f} min)")
        if best is None or sc > best[0]:
            best = (sc, ep + 1)
            torch.save({"model": model.state_dict(), "cfg": cfg, "epoch": ep + 1, "channels": channels}, run_dir / "best.pt")
    with open(run_dir / "history.json", "w") as f:
        json.dump(history, f, indent=2)

    # final valid evaluation of the best epoch, saved as the run's valid artefacts
    ck = torch.load(run_dir / "best.pt", map_location=device)
    model.load_state_dict(ck["model"])
    conf_m, rows = evaluate(model, sp["valid"], channels, norm, device, save_pred_dir=run_dir / "pred_valid")
    conf = metrics.Confusion()  # rebuild for save_split_results signature
    conf.tp, conf.fp, conf.fn, conf.tn = ({g: conf_m[g][k] for g in metrics.GROUPS} for k in ("tp", "fp", "fn", "tn"))
    m = experiments.save_split_results(LEVEL, run_id, "valid", conf, rows)
    params = {k: cfg[k] for k in cfg if k not in ("seed",)} | {"best_epoch": ck["epoch"], "plan": "v1.0"}
    experiments.log_row(LEVEL, run_id, "valid", cfg["model"], params, len(sp["valid"]), m,
                        note=f"best epoch {ck['epoch']} by frozen selection score {selection_score(m)[0]:.3f}")
    print(f"\n{run_id}: best epoch {ck['epoch']}  valid {fmt(m)}  score {selection_score(m)[0]:.3f}")
    return m


if __name__ == "__main__":
    assert_frozen()
    for p in sys.argv[1:]:
        train_one(pathlib.Path(p))
