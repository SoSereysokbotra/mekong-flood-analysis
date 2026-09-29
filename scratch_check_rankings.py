import json, csv

dist = json.load(open('results/level7/districts.json'))['districts']

methods = ['flood_cropland_otsu_vh_global', 'flood_cropland_unet_vv_ce', 'flood_cropland_unet_vvvh_cropw']

for m in methods:
    ranked = sorted(dist, key=lambda d: -d[m])
    print(m)
    for i, d in enumerate(ranked):
        print(f"  {i+1}. {d['district']}: {d[m]}")

print("\nWhat about total flood (not just cropland)?")
methods_tot = ['flood_otsu_vh_global', 'flood_unet_vv_ce', 'flood_unet_vvvh_cropw']
for m in methods_tot:
    ranked = sorted(dist, key=lambda d: -d[m])
    print(m)
    for i, d in enumerate(ranked):
        print(f"  {i+1}. {d['district']}: {d[m]}")
