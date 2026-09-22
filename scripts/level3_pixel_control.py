"""Level 3 control (evaluation_plan.md section 6.2): per-pixel classifiers on
(VV, VH, VV-VH, slope). No spatial context at all. If the U-Net cannot beat
this on bright recall at equal or better cropland precision, any U-Net gain
was "a better threshold", not context.

Two variants, both logged as level3 runs and selected like any candidate:
    pixel_logreg   logistic regression (linear decision boundary in 4-D)
    pixel_mlp      small MLP (non-linear boundary; still per-pixel)

Trained on a stratified pixel sample from the train split (balanced flood /
dry, 3M pixels), evaluated on every pixel of every valid chip. Test scoring
happens only through scripts/level3_test.py after a selection is recorded.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
from joblib import dump
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from tqdm import tqdm

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog, data, experiments, metrics  # noqa: E402

LEVEL = experiments.level3_dir()
FEATS = ["vv", "vh", "ratio", "slope"]
N_TRAIN_PX = 3_000_000


def features(ch: dict) -> np.ndarray:
    return np.stack([ch[c].ravel() for c in FEATS], 1).astype(np.float32)


def sample_train(chips, n_total, seed=0):
    rng = np.random.default_rng(seed)
    per_chip = n_total // len(chips)
    X, Y = [], []
    for chip in tqdm(chips, desc="sampling train", leave=False):
        ch, label, _, _ = data.raw_channels(chip)
        f, y = features(ch), label.ravel()
        finite = np.isfinite(f).all(1)  # RTC chips are NaN outside the slice footprint
        for cls in (0, 1):
            idx = np.flatnonzero((y == cls) & finite)
            if idx.size == 0:
                continue
            take = rng.choice(idx, min(per_chip // 2, idx.size), replace=False)
            X.append(f[take])
            Y.append(y[take])
    return np.concatenate(X), np.concatenate(Y)


def evaluate(clf, scaler, chips, save_dir=None):
    import rasterio

    conf, rows = metrics.Confusion(), []
    for chip in tqdm(chips, desc="eval", leave=False):
        ch, label, land, _ = data.raw_channels(chip)
        f = features(ch)
        finite = np.isfinite(f).all(1)
        prob = np.zeros(f.shape[0], np.float32)
        if finite.any():
            prob[finite] = clf.predict_proba(scaler.transform(f[finite]))[:, 1]
        pred = (prob >= 0.5).reshape(label.shape)
        label = np.where(finite.reshape(label.shape), label, -1).astype(np.int8)  # no radar -> not scorable
        c = metrics.Confusion().add(pred, label, land, vh=ch["vh"])
        conf.merge(c)
        cm = c.metrics()
        rows.append({"chip": chip, "event": catalog.s1f11_event(chip),
                     **{f"{g}_{k}": cm[g][k] for g in ("all", "cropland", "cropland_bright", "vegetation_bright", "open_water") for k in ("iou", "recall", "precision", "n_pos")}})
        if save_dir is not None:
            save_dir.mkdir(parents=True, exist_ok=True)
            label_tif = catalog.s1f11_paths(chip)["label"]
            if label_tif.exists():
                with rasterio.open(label_tif) as src:
                    prof = src.profile
                prof.update(dtype="uint8", count=1, compress="deflate", nodata=None)
                with rasterio.open(save_dir / f"{chip}.tif", "w", **prof) as dst:
                    dst.write(pred.astype(np.uint8), 1)
            else:
                np.save(save_dir / f"{chip}.npy", pred.astype(np.uint8))
    return conf, rows


def main():
    sp = data.splits()
    X, Y = sample_train(sp["train"], N_TRAIN_PX)
    scaler = StandardScaler().fit(X)
    Xs = scaler.transform(X)
    print(f"train sample: {len(Y):,} px, flood share {Y.mean():.3f}")
    runs = {
        "pixel_logreg": LogisticRegression(max_iter=500, C=1.0),
        "pixel_mlp": MLPClassifier(hidden_layer_sizes=(32, 32), max_iter=60, batch_size=4096, early_stopping=True, random_state=0),
    }
    for run_id, clf in runs.items():
        clf.fit(Xs, Y)
        run_dir = experiments.run_dir(LEVEL, run_id)
        dump({"clf": clf, "scaler": scaler, "feats": FEATS}, run_dir / "model.joblib")
        experiments.save_config(LEVEL, run_id, {"model": run_id, "features": FEATS, "n_train_px": int(len(Y)),
                                                "params": clf.get_params(), "control": "per-pixel, no spatial context"})
        conf, rows = evaluate(clf, scaler, sp["valid"], save_dir=run_dir / "pred_valid")
        m = experiments.save_split_results(LEVEL, run_id, "valid", conf, rows)
        experiments.log_row(LEVEL, run_id, "valid", run_id, {"features": FEATS, "plan": experiments.plan_version()}, len(sp["valid"]), m,
                            note="per-pixel control (evaluation_plan section 6.2)")
        print(f"{run_id:13s} valid: allIoU {m['all']['iou']:.3f} | crop IoU {m['cropland']['iou']:.3f} rec {m['cropland']['recall']:.3f} "
              f"prec {m['cropland']['precision']:.3f} | bright crop {m['cropland_bright']['recall']:.3f} veg {m['vegetation_bright']['recall']:.3f} "
              f"| dark {m['cropland_dark']['recall']:.3f}")


if __name__ == "__main__":
    main()
