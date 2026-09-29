import json, csv

dist = json.load(open('results/level7/districts.json'))
print('districts totals:', dist['totals'])
print('unassigned_km2:', dist['unassigned_km2'])
rep = json.load(open('results/level7/report.json'))
print('rep top3_share:', rep['top3_share'])

for d in dist['districts']:
    print(f"{d['district']:20s} crop:{d['cropland_km2']:6.1f} flood_crop_thr:{d['flood_cropland_otsu_vh_global']:6.1f} flood_crop_vv:{d['flood_cropland_unet_vv_ce']:6.1f} flood_crop_sel:{d['flood_cropland_unet_vvvh_cropw']:6.1f} post:{d['flood_cropland_post_unet_vvvh_cropw']:6.1f}")
