import json, csv, re, math

print("=== 1. CHECKING SUMMARY.md NUMBERS ===")

with open("results/level3_rtc/unet_vvvh_cropw/metrics_test.json") as f:
    sel = json.load(f)
print("Sel Level 3 test:", sel["cropland_bright"]["recall"], sel["vegetation_bright"]["recall"], sel["cropland"]["precision"], sel["all"]["iou"])

with open("results/level3_rtc/pixel_logreg/metrics_test.json") as f:
    pix = json.load(f)
print("Pix Level 3 test:", pix["cropland_bright"]["recall"], pix["vegetation_bright"]["recall"], pix["cropland"]["precision"], pix["all"]["iou"])

with open("results/level4/pipeline_switch.json") as f:
    ps = json.load(f)
print("Pipeline switch unet_vvvh_cropw on gamma0 all IoU:", ps["scores"]["unet_vvvh_cropw"]["gamma0"]["all"]["iou"])
print("Pipeline switch otsu_vh_global on gamma0:", ps["scores"]["otsu_vh_global"]["gamma0"]["cropland_bright"]["recall"], ps["scores"]["otsu_vh_global"]["gamma0"]["vegetation_bright"]["recall"], ps["scores"]["otsu_vh_global"]["gamma0"]["cropland"]["precision"], ps["scores"]["otsu_vh_global"]["gamma0"]["all"]["iou"])

with open("results/level4/bright_definition_check.json") as f:
    bdef = json.load(f)
print("Bright definition check unet_vvvh_cropw:", bdef["unet_vvvh_cropw"])

with open("results/level4/change_detection.json") as f:
    cd = json.load(f)
print("Change detection flood_peak_km2:", {k: v["flood_peak_km2"] for k, v in cd["methods"].items()})
print("Change detection flood_peak_cropland_km2:", {k: v["flood_peak_cropland_cropland_km2" if "flood_peak_cropland_cropland_km2" in v else "flood_peak_cropland_km2"] for k, v in cd["methods"].items()})
print("Change detection flood_post_cropland_km2:", {k: v.get("flood_post_cropland_km2") for k, v in cd["methods"].items()})

with open("results/level4/normal_years.json") as f:
    ny = json.load(f)
print("Normal years excess_2020_cropland_km2:", ny["excess_2020_cropland_km2"])

with open("results/level4/tierb_scores.json") as f:
    tb = json.load(f)
tot = tb["comparisons"]["total_water"]["methods"]
for m in ["otsu_vh_global", "unet_vv_ce", "unet_vvvh_cropw"]:
    print(f"Tier B total water {m}: IoU={tot[m]['cropland']['iou']:.3f}, rec={tot[m]['cropland']['recall']:.3f}, prec={tot[m]['cropland']['precision']:.3f}, all_prec={tot[m]['all']['precision']:.3f}")

print("Tier B total labelled water km2:", tb["comparisons"]["total_water"]["water_area_km2"])

with open("results/level4/hidden_water_feasibility.json") as f:
    hw = json.load(f)
print("Hidden water summary:", hw["summary"])

with open("results/level7/report.json") as f:
    rep = json.load(f)
print("Level 7 report.json summary:")
print("  fl:", rep["flood_km2"])
print("  fc:", rep["flood_cropland_km2"])
print("  top3_share:", rep["top3_share"])
print("  crop_post:", rep["flood_cropland_post_km2"])
print("  water_pre_km2:", rep["water_pre_km2"])
print("  water_peak_km2:", rep["water_peak_km2"])

with open("results/level7/districts.csv") as f:
    reader = csv.DictReader(f)
    dist_rows = list(reader)
print("Districts count:", len(dist_rows))
for r in dist_rows:
    print(r["district"], "cropland_km2:", r["cropland_km2"], "flood_cropland_unet_vvvh_cropw:", r["flood_cropland_unet_vvvh_cropw"], "post:", r["flood_cropland_post_unet_vvvh_cropw"])
