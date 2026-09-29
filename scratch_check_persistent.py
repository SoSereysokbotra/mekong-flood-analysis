import numpy as np
import rasterio

# Check the maps if available
import pathlib
maps_dir = pathlib.Path('results/level4/maps')
sel = 'unet_vvvh_cropw'
f_peak_path = maps_dir / f'flood_{sel}_2020-10-14_20m.tif'
f_post_path = maps_dir / f'flood_{sel}_2020-11-01_20m.tif'

if f_peak_path.exists() and f_post_path.exists():
    with rasterio.open(f_peak_path) as s1, rasterio.open(f_post_path) as s2:
        m_peak = s1.read(1) == 1
        m_post = s2.read(1) == 1
        
    still_standing = m_peak & m_post
    newly_flooded = ~m_peak & m_post
    drained = m_peak & ~m_post
    
    px_km2 = 0.0004
    print(f"Peak flood: {m_peak.sum() * px_km2:.1f} km2")
    print(f"Post flood (water on 1 Nov & ~26 Sep): {m_post.sum() * px_km2:.1f} km2")
    print(f"Actually still flooded (peak & post): {still_standing.sum() * px_km2:.1f} km2")
    print(f"Newly flooded after peak (~peak & post): {newly_flooded.sum() * px_km2:.1f} km2")
    print(f"Drained (peak & ~post): {drained.sum() * px_km2:.1f} km2")
else:
    print("Raster maps not present locally.")
