"""Build an interactive offline HTML gallery to view training and test chips.

Generates fast lightweight JPG previews in docs/gallery_assets/
and builds training_gallery.html in the project root.
"""
import csv
import json
import pathlib
import sys
from collections import defaultdict
from PIL import Image
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog, io, strata

ROOT = catalog.ROOT
ASSETS_DIR = ROOT / "docs" / "gallery_assets"
HTML_FILE = ROOT / "training_gallery.html"

def normalize_s2_rgb(s2: np.ndarray) -> np.ndarray:
    # S2 bands: Red=band 3, Green=band 2, Blue=band 1 (0-indexed)
    rgb = np.stack([s2[3], s2[2], s2[1]], axis=-1).astype(np.float32)
    rgb = np.clip(rgb / 2800.0, 0.0, 1.0)
    # subtle gamma correction
    rgb = np.power(rgb, 0.85)
    return (rgb * 255.0).astype(np.uint8)

def normalize_radar_vv(vv: np.ndarray) -> np.ndarray:
    # Clip dB between -25 and 0 dB
    clipped = np.clip(vv, -25.0, 0.0)
    norm = (clipped - (-25.0)) / 25.0
    return (norm * 255.0).astype(np.uint8)

def create_overlay(rgb_uint8: np.ndarray, label: np.ndarray) -> np.ndarray:
    out = rgb_uint8.copy()
    flood = label == 1
    # Tint floodwater electric blue
    out[flood, 0] = (out[flood, 0] * 0.25).astype(np.uint8)
    out[flood, 1] = (out[flood, 1] * 0.5 + 100).astype(np.uint8)
    out[flood, 2] = (out[flood, 2] * 0.3 + 178).astype(np.uint8)
    return out

def create_side_by_side(rgb: np.ndarray, radar_gray: np.ndarray, overlay: np.ndarray) -> np.ndarray:
    radar_rgb = np.stack([radar_gray, radar_gray, radar_gray], axis=-1)
    # Concatenate horizontally
    h, w, _ = rgb.shape
    banner = np.zeros((h, w * 3 + 4, 3), dtype=np.uint8)
    banner[:, :w] = rgb
    banner[:, w+2:w*2+2] = radar_rgb
    banner[:, w*2+4:] = overlay
    return banner

def main():
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Read inventory
    with open(ROOT / "docs" / "level0_inventory.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        
    by_event = defaultdict(list)
    for r in rows:
        by_event[r["event"]].append(r)
        
    # Pick top chips per country (sorted by flood area)
    selected_meta = []
    
    # Countries and how many chips to take
    quotas = {
        "India": 4, "Pakistan": 4, "Bolivia": 4, "Paraguay": 4,
        "Ghana": 4, "Sri-Lanka": 4, "Somalia": 4, "USA": 4,
        "Spain": 2, "Nigeria": 2, "Mekong": 4
    }
    
    for ev, q in quotas.items():
        event_chips = by_event[ev]
        # Sort by flooded cropland if available, else total flood
        event_chips.sort(key=lambda r: int(r["flood_cropland"]) * 2 + int(r["flood_open_water"]), reverse=True)
        selected_meta.extend(event_chips[:q])
        
    print(f"Generating image assets for {len(selected_meta)} curated chips...")
    
    chips_data = []
    
    for i, meta in enumerate(selected_meta):
        chip_id = meta["chip"]
        ev = meta["event"]
        split = meta["split"]
        
        try:
            s1, label, grid = io.read_s1f11_chip(chip_id)
            s2 = io.read_s1f11_s2(chip_id)
            
            rgb = normalize_s2_rgb(s2)
            radar = normalize_radar_vv(s1[0])
            overlay = create_overlay(rgb, label)
            composite = create_side_by_side(rgb, radar, overlay)
            
            # Save compressed jpgs
            comp_path = ASSETS_DIR / f"{chip_id}_comp.jpg"
            rgb_path = ASSETS_DIR / f"{chip_id}_rgb.jpg"
            radar_path = ASSETS_DIR / f"{chip_id}_radar.jpg"
            overlay_path = ASSETS_DIR / f"{chip_id}_overlay.jpg"
            
            # Resize composite for fast browser loading
            im_comp = Image.fromarray(composite).resize((768, 256), Image.Resampling.BILINEAR)
            im_comp.save(comp_path, quality=80)
            
            Image.fromarray(rgb).save(rgb_path, quality=85)
            Image.fromarray(radar).save(radar_path, quality=85)
            Image.fromarray(overlay).save(overlay_path, quality=85)
            
            f_crop = int(meta["flood_cropland"])
            f_water = int(meta["flood_open_water"])
            f_veg = int(meta["flood_vegetation"])
            f_total = f_crop + f_water + f_veg + int(meta["flood_built"]) + int(meta["flood_other"])
            
            chips_data.append({
                "id": chip_id,
                "event": ev,
                "split": split,
                "flood_total": f_total,
                "flood_crop": f_crop,
                "flood_water": f_water,
                "flood_veg": f_veg,
                "comp_url": f"docs/gallery_assets/{chip_id}_comp.jpg",
                "rgb_url": f"docs/gallery_assets/{chip_id}_rgb.jpg",
                "radar_url": f"docs/gallery_assets/{chip_id}_radar.jpg",
                "overlay_url": f"docs/gallery_assets/{chip_id}_overlay.jpg",
            })
            print(f"[{i+1}/{len(selected_meta)}] Processed {chip_id} ({ev})")
        except Exception as e:
            print(f"Failed on {chip_id}: {e}")
            
    # Write HTML
    html_content = generate_html(chips_data)
    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"\nSUCCESS! Created gallery at: {HTML_FILE}")

def generate_html(chips_data):
    data_json = json.dumps(chips_data)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mekong Flood Intelligence — Training Data Gallery</title>
    <style>
        :root {{
            --bg: #0f172a;
            --surface: #1e293b;
            --surface-hover: #334155;
            --border: #334155;
            --primary: #38bdf8;
            --text: #f8fafc;
            --text-dim: #94a3b8;
            --accent-blue: #0284c7;
            --accent-green: #22c55e;
            --accent-yellow: #eab308;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            padding: 24px;
            line-height: 1.5;
        }}
        header {{
            max-width: 1400px;
            margin: 0 auto 28px;
            border-bottom: 1px solid var(--border);
            padding-bottom: 20px;
        }}
        .header-title {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 16px;
        }}
        h1 {{
            font-size: 26px;
            font-weight: 700;
            color: var(--text);
        }}
        h1 span {{ color: var(--primary); }}
        .subtitle {{
            color: var(--text-dim);
            font-size: 14px;
            margin-top: 4px;
        }}
        .badge {{
            padding: 4px 10px;
            border-radius: 9999px;
            font-size: 12px;
            font-weight: 600;
        }}
        .badge-train {{ background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid #0284c7; }}
        .badge-test {{ background: rgba(234, 179, 8, 0.15); color: #facc15; border: 1px solid #ca8a04; }}
        .badge-valid {{ background: rgba(34, 197, 94, 0.15); color: #4ade80; border: 1px solid #16a34a; }}

        /* Controls */
        .controls {{
            max-width: 1400px;
            margin: 0 auto 24px;
            display: flex;
            flex-direction: column;
            gap: 16px;
            background: var(--surface);
            padding: 16px;
            border-radius: 12px;
            border: 1px solid var(--border);
        }}
        .filter-row {{
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .filter-label {{
            font-size: 13px;
            font-weight: 600;
            color: var(--text-dim);
            margin-right: 6px;
            min-width: 70px;
        }}
        .btn {{
            background: var(--bg);
            border: 1px solid var(--border);
            color: var(--text);
            padding: 6px 14px;
            border-radius: 6px;
            font-size: 13px;
            cursor: pointer;
            transition: all 0.15s ease;
        }}
        .btn:hover {{ background: var(--surface-hover); }}
        .btn.active {{
            background: var(--primary);
            color: #0f172a;
            font-weight: 600;
            border-color: var(--primary);
        }}

        /* Legend */
        .legend {{
            display: flex;
            gap: 20px;
            font-size: 13px;
            color: var(--text-dim);
            align-items: center;
        }}
        .legend-item {{ display: flex; align-items: center; gap: 6px; }}
        .legend-color {{ width: 12px; height: 12px; border-radius: 3px; }}

        /* Grid */
        .grid {{
            max-width: 1400px;
            margin: 0 auto;
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
            gap: 20px;
        }}
        .card {{
            background: var(--surface);
            border-radius: 10px;
            border: 1px solid var(--border);
            overflow: hidden;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);
            border-color: #475569;
        }}
        .card-header {{
            padding: 12px 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid var(--border);
        }}
        .card-title {{
            font-size: 14px;
            font-weight: 600;
        }}
        .card-body {{
            position: relative;
            background: #000;
            cursor: pointer;
            aspect-ratio: 3 / 1;
        }}
        .card-img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
            display: block;
        }}
        .labels-strip {{
            display: flex;
            justify-content: space-around;
            padding: 6px;
            background: #111827;
            font-size: 11px;
            font-weight: 600;
            color: #94a3b8;
            border-top: 1px solid var(--border);
        }}
        .card-footer {{
            padding: 12px 16px;
            font-size: 12px;
            color: var(--text-dim);
            display: flex;
            justify-content: space-between;
        }}
        .stat-val {{
            color: var(--text);
            font-weight: 600;
        }}

        /* Modal */
        .modal {{
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(15, 23, 42, 0.92);
            backdrop-filter: blur(4px);
            z-index: 100;
            align-items: center;
            justify-content: center;
            padding: 24px;
        }}
        .modal-content {{
            max-width: 900px;
            width: 100%;
            background: var(--surface);
            border-radius: 12px;
            border: 1px solid var(--border);
            overflow: hidden;
            position: relative;
        }}
        .modal-close {{
            position: absolute;
            top: 14px;
            right: 18px;
            font-size: 24px;
            color: var(--text-dim);
            cursor: pointer;
            z-index: 10;
        }}
        .modal-img-wrap {{
            background: #000;
            text-align: center;
        }}
        .modal-img {{
            max-height: 70vh;
            max-width: 100%;
            display: inline-block;
        }}
        .modal-footer {{
            padding: 16px 20px;
        }}
    </style>
</head>
<body>

    <header>
        <div class="header-title">
            <div>
                <h1>Mekong Flood Intelligence <span>Training Data Gallery</span></h1>
                <div class="subtitle">Exploring Sen1Floods11 benchmark scenes across 8 countries & held-out test data</div>
            </div>
            <div>
                <span class="badge badge-train">368 Training Chips</span>
                <span class="badge badge-valid">48 Valid Chips</span>
                <span class="badge badge-test">30 Held-Out Test Chips</span>
            </div>
        </div>
    </header>

    <div class="controls">
        <div class="filter-row">
            <span class="filter-label">Country:</span>
            <button class="btn active" onclick="filterCountry('ALL')">All Countries</button>
            <button class="btn" onclick="filterCountry('India')">India (Train)</button>
            <button class="btn" onclick="filterCountry('Pakistan')">Pakistan (Train)</button>
            <button class="btn" onclick="filterCountry('USA')">USA (Train)</button>
            <button class="btn" onclick="filterCountry('Bolivia')">Bolivia (Train)</button>
            <button class="btn" onclick="filterCountry('Paraguay')">Paraguay (Train)</button>
            <button class="btn" onclick="filterCountry('Ghana')">Ghana (Train)</button>
            <button class="btn" onclick="filterCountry('Sri-Lanka')">Sri Lanka (Train)</button>
            <button class="btn" onclick="filterCountry('Somalia')">Somalia (Train)</button>
            <button class="btn" onclick="filterCountry('Mekong')">Cambodia (Held-out Test)</button>
        </div>
        <div class="filter-row">
            <span class="filter-label">Display:</span>
            <button class="btn active" onclick="switchView('comp')">3-in-1 Composite (Optical | Radar | Flood)</button>
            <button class="btn" onclick="switchView('rgb')">Optical RGB Only</button>
            <button class="btn" onclick="switchView('radar')">Radar VV Only</button>
            <button class="btn" onclick="switchView('overlay')">Flood Overlay (Blue = Flood)</button>
        </div>
        <div class="legend">
            <div class="legend-item"><div class="legend-color" style="background: #38bdf8;"></div> Flooded Area (Ground Truth)</div>
            <div class="legend-item"><div class="legend-color" style="background: #eab308;"></div> Flooded Rice / Farmland</div>
            <div class="legend-item"><div class="legend-color" style="background: #22c55e;"></div> Flooded Vegetation / Trees</div>
        </div>
    </div>

    <div class="grid" id="cardGrid"></div>

    <div class="modal" id="imageModal" onclick="closeModal()">
        <div class="modal-content" onclick="event.stopPropagation()">
            <div class="modal-close" onclick="closeModal()">&times;</div>
            <div class="modal-img-wrap">
                <img id="modalImg" class="modal-img" src="" alt="Enlarged view">
            </div>
            <div class="modal-footer" id="modalText"></div>
        </div>
    </div>

    <script>
        const CHIPS = {data_json};
        let currentCountry = 'ALL';
        let currentView = 'comp'; // comp, rgb, radar, overlay

        function renderCards() {{
            const grid = document.getElementById('cardGrid');
            grid.innerHTML = '';
            
            const filtered = CHIPS.filter(c => currentCountry === 'ALL' || c.event === currentCountry);
            
            filtered.forEach(chip => {{
                let imgSrc = chip.comp_url;
                if (currentView === 'rgb') imgSrc = chip.rgb_url;
                if (currentView === 'radar') imgSrc = chip.radar_url;
                if (currentView === 'overlay') imgSrc = chip.overlay_url;
                
                const badgeClass = chip.split === 'train' ? 'badge-train' : (chip.split === 'test' ? 'badge-test' : 'badge-valid');
                
                const card = document.createElement('div');
                card.className = 'card';
                card.innerHTML = `
                    <div class="card-header">
                        <span class="card-title">${{chip.event}} — ${{chip.id}}</span>
                        <span class="badge ${{badgeClass}}">${{chip.split.toUpperCase()}}</span>
                    </div>
                    <div class="card-body" onclick="openModal('${{chip.id}}', '${{imgSrc}}', '${{chip.event}}')">
                        <img class="card-img" src="${{imgSrc}}" alt="${{chip.id}}" loading="lazy">
                    </div>
                    ${{currentView === 'comp' ? '<div class="labels-strip"><span>1. OPTICAL RGB</span><span>2. RADAR VV</span><span>3. FLOOD OVERLAY</span></div>' : ''}}
                    <div class="card-footer">
                        <div>Crop flood: <span class="stat-val">${{chip.flood_crop.toLocaleString()}} px</span></div>
                        <div>Water flood: <span class="stat-val">${{chip.flood_water.toLocaleString()}} px</span></div>
                        <div>Total flood: <span class="stat-val">${{chip.flood_total.toLocaleString()}} px</span></div>
                    </div>
                `;
                grid.appendChild(card);
            }});
        }}

        function filterCountry(country) {{
            currentCountry = country;
            document.querySelectorAll('.filter-row:nth-child(1) .btn').forEach(b => {{
                b.classList.toggle('active', b.textContent.includes(country) || (country === 'ALL' && b.textContent.includes('All')));
            }});
            renderCards();
        }}

        function switchView(view) {{
            currentView = view;
            document.querySelectorAll('.filter-row:nth-child(2) .btn').forEach(b => {{
                b.classList.remove('active');
            }});
            event.target.classList.add('active');
            renderCards();
        }}

        function openModal(id, src, eventName) {{
            const modal = document.getElementById('imageModal');
            const img = document.getElementById('modalImg');
            const txt = document.getElementById('modalText');
            img.src = src;
            txt.innerHTML = `<strong>${{eventName}} (${{id}})</strong> — Click outside to close`;
            modal.style.display = 'flex';
        }}

        function closeModal() {{
            document.getElementById('imageModal').style.display = 'none';
        }}

        // Initial render
        renderCards();
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
