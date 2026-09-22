"""Level 2: where does the baseline fail, and why?

Re-scores the *saved* Level 1 predictions of the selected baseline
(otsu_vh_global) and sorts every false positive and false negative into a
physical category using land type, terrain slope (Copernicus DEM, metres) and
the JRC permanent-water layer shipped with each chip.

False positives (predicted water, labelled dry), first match wins:
    fp_jrc_permanent_water   JRC says permanent water; label says dry   -> label / reference disagreement
    fp_wc_open_water         WorldCover says water; label says dry      -> label / land-cover disagreement
    fp_terrain               slope >= SLOPE_DEG                          -> radar shadow / layover on hills
    fp_smooth_built_other    built-up or bare                            -> smooth surfaces reflect away
    fp_dry_cropland          flat cropland                               -> wet soil, harvested / ploughed paddy
    fp_dry_vegetation        flat vegetation
    fp_unknown

False negatives (labelled water, predicted dry). For a VH threshold every FN is
by construction VH-bright, so the categories are land types, and each is split
by whether VV is *also* bright (unrecoverable by any single-band threshold) or
VV is dark (recoverable by dual-pol logic):
    fn_bright_cropland, fn_bright_vegetation, fn_rough_open_water, fn_built, fn_other
    each with _vv_dark / _vv_bright sub-counts

Also writes:
    results/level2/mekong_bright_per_chip.csv   where the ~50k bright test pixels sit
    results/level2/joint_hist.npz               2-D (VV, VH) histograms, flooded vs dry cropland, per split
    results/level2/separability.json            single-feature AUC of VV, VH, VV-VH for bright flooded vs dry cropland

Everything downstream (figures, the note, X and Y) is generated from these files.
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys

import numpy as np
import rasterio
from tqdm import tqdm

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog, experiments, io, metrics, strata  # noqa: E402

LEVEL = "level2"
BASELINE = "otsu_vh_global"
SLOPE_DEG = 8.0
OUT = experiments.RESULTS / LEVEL
VH_T = metrics.BRIGHT_VH_DB


def vv_threshold() -> float:
    with open(experiments.run_dir("level1", "_global_thresholds") / "config.json") as f:
        return float(json.load(f)["vv"])


FP_CATS = ["fp_jrc_permanent_water", "fp_wc_open_water", "fp_terrain", "fp_smooth_built_other",
           "fp_dry_cropland", "fp_dry_vegetation", "fp_unknown"]
FN_LANDS = {"fn_bright_cropland": strata.CROPLAND, "fn_bright_vegetation": strata.VEGETATION,
            "fn_rough_open_water": strata.OPEN_WATER, "fn_built": strata.BUILT}
FN_CATS = list(FN_LANDS) + ["fn_other"]


def categorise(pred, label, land, slope, jrc, vv, vv_t) -> dict[str, int]:
    valid = label >= 0
    fp = pred & (label == 0) & valid
    fn = ~pred & (label == 1) & valid
    out = {}
    left = fp.copy()
    for cat, mask in [
        ("fp_jrc_permanent_water", jrc == 1),
        ("fp_wc_open_water", land == strata.OPEN_WATER),
        ("fp_terrain", slope >= SLOPE_DEG),
        ("fp_smooth_built_other", (land == strata.BUILT) | (land == strata.OTHER)),
        ("fp_dry_cropland", land == strata.CROPLAND),
        ("fp_dry_vegetation", land == strata.VEGETATION),
    ]:
        m = left & mask
        out[cat] = int(m.sum())
        left &= ~m
    out["fp_unknown"] = int(left.sum())
    left = fn.copy()
    for cat, code in FN_LANDS.items():
        m = left & (land == code)
        out[cat] = int(m.sum())
        out[cat + "_vv_dark"] = int((m & (vv < vv_t)).sum())
        out[cat + "_vv_bright"] = int((m & (vv >= vv_t)).sum())
        left &= ~m
    out["fn_other"] = int(left.sum())
    out["fn_other_vv_dark"] = int((left & (vv < vv_t)).sum())
    out["fn_other_vv_bright"] = int((left & (vv >= vv_t)).sum())
    out["fp_total"], out["fn_total"] = int(fp.sum()), int(fn.sum())
    out["tp_total"] = int((pred & (label == 1) & valid).sum())
    return out


def auc_rank(pos: np.ndarray, neg: np.ndarray) -> float:
    """Mann-Whitney AUC: P(score(pos) > score(neg)). 0.5 = no information."""
    from scipy.stats import rankdata

    x = np.concatenate([pos, neg])
    r = rankdata(x)
    n1, n0 = len(pos), len(neg)
    return float((r[:n1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def main():
    vv_t = vv_threshold()
    split = catalog.s1f11_split()
    OUT.mkdir(parents=True, exist_ok=True)
    pred_dir = experiments.run_dir("level1", BASELINE) / "pred"
    edges = np.arange(-40, 5.5, 0.5)
    joint = {}
    taxonomy, per_chip, sep, bright_rows = {}, [], {}, []
    rng = np.random.default_rng(0)

    for s, chips in split.items():
        tot = {}
        H = {cls: np.zeros((len(edges) - 1, len(edges) - 1), np.int64) for cls in ("flood", "dry")}
        feat = {cls: {"vv": [], "vh": []} for cls in ("bright_flood", "dry")}
        for chip in tqdm(chips, desc=s, leave=False):
            s1, label, grid = io.read_s1f11_chip(chip)
            land = strata.land_type(io.worldcover_chip(chip, grid))
            slope = io.slope_deg(io.dem_chip(chip, grid), grid)
            jrc = io.read_s1f11_layer(chip, "jrc")
            with rasterio.open(pred_dir / f"{chip}.tif") as src:
                pred = src.read(1).astype(bool)
            vv, vh = s1[0], s1[1]
            c = categorise(pred, label, land, slope, jrc, vv, vv_t)
            per_chip.append({"chip": chip, "event": catalog.s1f11_event(chip), "split": s,
                             "slope_p90": float(np.nanpercentile(slope, 90)), **c})
            for k, v in c.items():
                tot[k] = tot.get(k, 0) + v
            crop = land == strata.CROPLAND
            fl, dr = (label == 1) & crop, (label == 0) & crop
            H["flood"] += np.histogram2d(np.clip(vv[fl], -40, 5), np.clip(vh[fl], -40, 5), [edges, edges])[0].astype(np.int64)
            H["dry"] += np.histogram2d(np.clip(vv[dr], -40, 5), np.clip(vh[dr], -40, 5), [edges, edges])[0].astype(np.int64)
            bf = fl & (vh >= VH_T)
            for cls, m in (("bright_flood", bf), ("dry", dr)):
                idx = np.flatnonzero(m)
                if idx.size > 2000:
                    idx = rng.choice(idx, 2000, replace=False)
                feat[cls]["vv"].append(vv.ravel()[idx])
                feat[cls]["vh"].append(vh.ravel()[idx])
            if s == "test":
                bright_rows.append({
                    "chip": chip, "n_crop_flood": int(fl.sum()), "n_bright": int(bf.sum()),
                    "frac_bright": float(bf.sum() / max(fl.sum(), 1)),
                    "bright_vv_median": float(np.median(vv[bf])) if bf.any() else float("nan"),
                    "bright_vh_median": float(np.median(vh[bf])) if bf.any() else float("nan"),
                    "bright_frac_vv_dark": float((vv[bf] < vv_t).mean()) if bf.any() else float("nan"),
                    "dry_crop_vv_median": float(np.median(vv[dr])) if dr.any() else float("nan"),
                })
        taxonomy[s] = tot
        for cls in H:
            joint[f"{s}/{cls}"] = H[cls]
        pos = {b: np.concatenate(feat["bright_flood"][b]) for b in ("vv", "vh")}
        neg = {b: np.concatenate(feat["dry"][b]) for b in ("vv", "vh")}
        # lower value => more water-like, so score = -feature for VV/VH; ratio VV-VH: flooded vegetation
        # (double bounce) is expected to raise VV more than VH, so higher VV-VH => more flood-like
        sep[s] = {
            "n_bright_flood": int(len(pos["vv"])), "n_dry": int(len(neg["vv"])),
            "auc_vv_darker": auc_rank(-pos["vv"], -neg["vv"]),
            "auc_vh_darker": auc_rank(-pos["vh"], -neg["vh"]),
            "auc_vv_minus_vh_higher": auc_rank(pos["vv"] - pos["vh"], neg["vv"] - neg["vh"]),
            "bright_flood_vv_median": float(np.median(pos["vv"])), "dry_vv_median": float(np.median(neg["vv"])),
            "bright_flood_vh_median": float(np.median(pos["vh"])), "dry_vh_median": float(np.median(neg["vh"])),
            "bright_flood_ratio_median": float(np.median(pos["vv"] - pos["vh"])), "dry_ratio_median": float(np.median(neg["vv"] - neg["vh"])),
        }

    with open(OUT / "failure_taxonomy.json", "w") as f:
        json.dump({"baseline": BASELINE, "slope_deg": SLOPE_DEG, "vh_threshold": VH_T, "vv_threshold": vv_t,
                   "fp_categories": FP_CATS, "fn_categories": FN_CATS, "splits": taxonomy}, f, indent=2)
    with open(OUT / "failure_per_chip.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(per_chip[0].keys()))
        w.writeheader()
        w.writerows(per_chip)
    with open(OUT / "mekong_bright_per_chip.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(bright_rows[0].keys()))
        w.writeheader()
        w.writerows(sorted(bright_rows, key=lambda r: -r["n_bright"]))
    np.savez_compressed(OUT / "joint_hist.npz", edges=edges, **joint)
    with open(OUT / "separability.json", "w") as f:
        json.dump(sep, f, indent=2)

    for s in ("train", "valid", "test"):
        t = taxonomy[s]
        print(f"\n== {s}: FP {t['fp_total']:,}  FN {t['fn_total']:,}  TP {t['tp_total']:,} ==")
        for c in FP_CATS:
            print(f"  {c:26s} {t[c]:10,d}  {100 * t[c] / max(t['fp_total'], 1):5.1f}% of FP")
        for c in FN_CATS:
            print(f"  {c:26s} {t[c]:10,d}  {100 * t[c] / max(t['fn_total'], 1):5.1f}% of FN   "
                  f"(VV dark {t[c + '_vv_dark']:,} / VV bright {t[c + '_vv_bright']:,})")
        print(f"  separability bright-flooded vs dry cropland: AUC VV {sep[s]['auc_vv_darker']:.3f}  "
              f"VH {sep[s]['auc_vh_darker']:.3f}  VV-VH {sep[s]['auc_vv_minus_vh_higher']:.3f}")
    print("\nMekong bright pixels per chip (top 8):")
    for r in sorted(bright_rows, key=lambda r: -r["n_bright"])[:8]:
        print(f"  {r['chip']:16s} bright {r['n_bright']:7,d} / {r['n_crop_flood']:8,d} ({r['frac_bright']:5.1%})  "
              f"VV med {r['bright_vv_median']:6.1f} (dry {r['dry_crop_vv_median']:6.1f})  VV-dark {r['bright_frac_vv_dark']:5.1%}")


if __name__ == "__main__":
    main()
