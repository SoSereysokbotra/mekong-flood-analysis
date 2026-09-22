"""Build an interactive offline HTML gallery to view ALL 446 training, validation, and test chips.

Generates lightweight JPG previews in docs/gallery_assets/
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
    rgb = np.power(rgb, 0.85)
    return (rgb * 255.0).astype(np.uint8)

def normalize_radar_vv(vv: np.ndarray) -> np.ndarray:
    clipped = np.clip(vv, -25.0, 0.0)
    norm = (clipped - (-25.0)) / 25.0
    return (norm * 255.0).astype(np.uint8)

def create_overlay(rgb_uint8: np.ndarray, label: np.ndarray) -> np.ndarray:
    out = rgb_uint8.copy()
    flood = label == 1
    out[flood, 0] = (out[flood, 0] * 0.25).astype(np.uint8)
    out[flood, 1] = (out[flood, 1] * 0.5 + 100).astype(np.uint8)
    out[flood, 2] = (out[flood, 2] * 0.3 + 178).astype(np.uint8)
    return out

def create_side_by_side(rgb: np.ndarray, radar_gray: np.ndarray, overlay: np.ndarray) -> np.ndarray:
    radar_rgb = np.stack([radar_gray, radar_gray, radar_gray], axis=-1)
    h, w, _ = rgb.shape
    banner = np.zeros((h, w * 3 + 4, 3), dtype=np.uint8)
    banner[:, :w] = rgb
    banner[:, w+2:w*2+2] = radar_rgb
    banner[:, w*2+4:] = overlay
    return banner

def main():
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    
    with open(ROOT / "docs" / "level0_inventory.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        
    print(f"Processing ALL {len(rows)} chips across the entire dataset...")
    
    chips_data = []
    
    for i, meta in enumerate(rows):
        chip_id = meta["chip"]
        ev = meta["event"]
        split = meta["split"]
        
        comp_path = ASSETS_DIR / f"{chip_id}_comp.jpg"
        rgb_path = ASSETS_DIR / f"{chip_id}_rgb.jpg"
        radar_path = ASSETS_DIR / f"{chip_id}_radar.jpg"
        overlay_path = ASSETS_DIR / f"{chip_id}_overlay.jpg"
        
        # Check if assets already exist to speed up re-runs
        if not (comp_path.exists() and rgb_path.exists() and radar_path.exists() and overlay_path.exists()):
            try:
                s1, label, grid = io.read_s1f11_chip(chip_id)
                s2 = io.read_s1f11_s2(chip_id)
                
                rgb = normalize_s2_rgb(s2)
                radar = normalize_radar_vv(s1[0])
                overlay = create_overlay(rgb, label)
                composite = create_side_by_side(rgb, radar, overlay)
                
                im_comp = Image.fromarray(composite).resize((768, 256), Image.Resampling.BILINEAR)
                im_comp.save(comp_path, quality=80)
                
                Image.fromarray(rgb).save(rgb_path, quality=85)
                Image.fromarray(radar).save(radar_path, quality=85)
                Image.fromarray(overlay).save(overlay_path, quality=85)
            except Exception as e:
                print(f"Error on {chip_id}: {e}")
                continue
                
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
        if (i + 1) % 50 == 0 or (i + 1) == len(rows):
            print(f"Progress: [{i+1}/{len(rows)}] chips ready")
            
    html_content = generate_html(chips_data)
    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"\nALL DONE! Complete gallery with {len(chips_data)} chips written to: {HTML_FILE}")

def generate_html(chips_data):
    data_json = json.dumps(chips_data)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mekong Flood Intelligence — Complete 446-Chip Gallery</title>
    <style>
        :root {{
            --bg: #0b1120;
            --surface: #1e293b;
            --surface-hover: #334155;
            --border: #334155;
            --primary: #38bdf8;
            --text: #f8fafc;
            --text-dim: #94a3b8;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            padding: 20px;
            line-height: 1.5;
        }}
        header {{
            max-width: 1440px;
            margin: 0 auto 20px;
            border-bottom: 1px solid var(--border);
            padding-bottom: 16px;
        }}
        .header-title {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 16px;
        }}
        h1 {{ font-size: 24px; font-weight: 700; }}
        h1 span {{ color: var(--primary); }}
        .subtitle {{ color: var(--text-dim); font-size: 13px; margin-top: 2px; }}
        .badge {{
            padding: 3px 10px;
            border-radius: 9999px;
            font-size: 12px;
            font-weight: 600;
        }}
        .badge-train {{ background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid #0284c7; }}
        .badge-test {{ background: rgba(234, 179, 8, 0.15); color: #facc15; border: 1px solid #ca8a04; }}
        .badge-valid {{ background: rgba(34, 197, 94, 0.15); color: #4ade80; border: 1px solid #16a34a; }}

        .controls {{
            max-width: 1440px;
            margin: 0 auto 20px;
            display: flex;
            flex-direction: column;
            gap: 12px;
            background: var(--surface);
            padding: 16px;
            border-radius: 10px;
            border: 1px solid var(--border);
        }}
        .filter-row {{
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 6px;
        }}
        .filter-label {{
            font-size: 12px;
            font-weight: 700;
            color: var(--text-dim);
            min-width: 60px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .btn {{
            background: var(--bg);
            border: 1px solid var(--border);
            color: var(--text);
            padding: 5px 11px;
            border-radius: 6px;
            font-size: 12px;
            cursor: pointer;
            transition: all 0.12s ease;
        }}
        .btn:hover {{ background: var(--surface-hover); }}
        .btn.active {{
            background: var(--primary);
            color: #0b1120;
            font-weight: 700;
            border-color: var(--primary);
        }}
        .search-box {{
            background: var(--bg);
            border: 1px solid var(--border);
            color: var(--text);
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 13px;
            width: 220px;
            outline: none;
        }}
        .search-box:focus {{ border-color: var(--primary); }}

        .status-bar {{
            font-size: 13px;
            color: var(--text-dim);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .grid {{
            max-width: 1440px;
            margin: 0 auto;
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(430px, 1fr));
            gap: 18px;
        }}
        .card {{
            background: var(--surface);
            border-radius: 8px;
            border: 1px solid var(--border);
            overflow: hidden;
            transition: transform 0.15s, border-color 0.15s;
        }}
        .card:hover {{
            transform: translateY(-2px);
            border-color: #64748b;
        }}
        .card-header {{
            padding: 10px 14px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid var(--border);
        }}
        .card-title {{ font-size: 13px; font-weight: 600; }}
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
            padding: 4px;
            background: #090e17;
            font-size: 10px;
            font-weight: 700;
            color: #64748b;
            border-top: 1px solid var(--border);
            letter-spacing: 0.5px;
        }}
        .card-footer {{
            padding: 10px 14px;
            font-size: 11px;
            color: var(--text-dim);
            display: flex;
            justify-content: space-between;
        }}
        .stat-val {{ color: var(--text); font-weight: 600; }}

        .modal {{
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(11, 17, 32, 0.94);
            backdrop-filter: blur(4px);
            z-index: 100;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .modal-content {{
            max-width: 960px;
            width: 100%;
            background: var(--surface);
            border-radius: 10px;
            border: 1px solid var(--border);
            overflow: hidden;
            position: relative;
        }}
        .modal-close {{
            position: absolute;
            top: 10px;
            right: 16px;
            font-size: 26px;
            color: var(--text-dim);
            cursor: pointer;
            z-index: 10;
        }}
        .modal-img-wrap {{ background: #000; text-align: center; }}
        .modal-img {{ max-height: 72vh; max-width: 100%; display: inline-block; }}
        .modal-footer {{ padding: 14px 18px; font-size: 13px; }}
    </style>
</head>
<body>

    <header>
        <div class="header-title">
            <div>
                <h1>Mekong Flood Intelligence <span>Complete Dataset Browser</span></h1>
                <div class="subtitle">Every chip in Sen1Floods11: 368 Training, 48 Validation, 30 Cambodia Held-Out Test</div>
            </div>
            <div>
                <span class="badge badge-train">368 Train</span>
                <span class="badge badge-valid">48 Valid</span>
                <span class="badge badge-test">30 Test</span>
            </div>
        </div>
    </header>

    <div class="controls">
        <div class="filter-row">
            <span class="filter-label">Split:</span>
            <button class="btn active" onclick="filterSplit('ALL')">All (446)</button>
            <button class="btn" onclick="filterSplit('train')">Training (368)</button>
            <button class="btn" onclick="filterSplit('valid')">Validation (48)</button>
            <button class="btn" onclick="filterSplit('test')">Held-Out Test (30)</button>
        </div>
        <div class="filter-row">
            <span class="filter-label">Country:</span>
            <button class="btn active" onclick="filterCountry('ALL')">All Countries</button>
            <button class="btn" onclick="filterCountry('India')">India (68)</button>
            <button class="btn" onclick="filterCountry('USA')">USA (69)</button>
            <button class="btn" onclick="filterCountry('Paraguay')">Paraguay (67)</button>
            <button class="btn" onclick="filterCountry('Ghana')">Ghana (53)</button>
            <button class="btn" onclick="filterCountry('Sri-Lanka')">Sri Lanka (42)</button>
            <button class="btn" onclick="filterCountry('Pakistan')">Pakistan (28)</button>
            <button class="btn" onclick="filterCountry('Somalia')">Somalia (26)</button>
            <button class="btn" onclick="filterCountry('Bolivia')">Bolivia (15)</button>
            <button class="btn" onclick="filterCountry('Spain')">Spain (24)</button>
            <button class="btn" onclick="filterCountry('Nigeria')">Nigeria (24)</button>
            <button class="btn" onclick="filterCountry('Mekong')">Cambodia (30)</button>
        </div>
        <div class="filter-row" style="justify-content: space-between;">
            <div style="display: flex; align-items: center; gap: 6px;">
                <span class="filter-label">Layer:</span>
                <button class="btn active" onclick="switchView('comp')">3-in-1 (Optical | Radar | Flood)</button>
                <button class="btn" onclick="switchView('rgb')">Optical RGB</button>
                <button class="btn" onclick="switchView('radar')">Radar VV</button>
                <button class="btn" onclick="switchView('overlay')">Flood Overlay</button>
            </div>
            <input type="text" id="searchInput" class="search-box" placeholder="Search chip name..." oninput="handleSearch()">
        </div>
        <div class="status-bar">
            <span id="counterText">Showing 446 of 446 chips</span>
            <span>Blue = Actual Floodwater | Green = Vegetation | Gray = Radar Echo</span>
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
        let currentSplit = 'ALL';
        let currentCountry = 'ALL';
        let currentView = 'comp';
        let searchQuery = '';

        function renderCards() {{
            const grid = document.getElementById('cardGrid');
            grid.innerHTML = '';
            
            const filtered = CHIPS.filter(c => {{
                const matchSplit = currentSplit === 'ALL' || c.split === currentSplit;
                const matchCountry = currentCountry === 'ALL' || c.event === currentCountry;
                const matchSearch = searchQuery === '' || c.id.toLowerCase().includes(searchQuery.toLowerCase());
                return matchSplit && matchCountry && matchSearch;
            }});

            document.getElementById('counterText').textContent = `Showing ${{filtered.length}} of ${{CHIPS.length}} chips`;
            
            // Render first 100 instantly, then rest on demand or lazy
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
                    ${{currentView === 'comp' ? '<div class="labels-strip"><span>OPTICAL RGB</span><span>RADAR VV</span><span>FLOOD OVERLAY</span></div>' : ''}}
                    <div class="card-footer">
                        <div>Crops: <span class="stat-val">${{chip.flood_crop.toLocaleString()}} px</span></div>
                        <div>Water: <span class="stat-val">${{chip.flood_water.toLocaleString()}} px</span></div>
                        <div>Total: <span class="stat-val">${{chip.flood_total.toLocaleString()}} px</span></div>
                    </div>
                `;
                grid.appendChild(card);
            }});
        }}

        function filterSplit(split) {{
            currentSplit = split;
            document.querySelectorAll('.filter-row:nth-child(1) .btn').forEach(b => {{
                b.classList.toggle('active', b.textContent.toLowerCase().includes(split.toLowerCase()) || (split === 'ALL' && b.textContent.includes('All')));
            }});
            renderCards();
        }}

        function filterCountry(country) {{
            currentCountry = country;
            document.querySelectorAll('.filter-row:nth-child(2) .btn').forEach(b => {{
                b.classList.toggle('active', b.textContent.includes(country) || (country === 'ALL' && b.textContent.includes('All')));
            }});
            renderCards();
        }}

        function switchView(view) {{
            currentView = view;
            document.querySelectorAll('.filter-row:nth-child(3) .btn').forEach(b => {{
                b.classList.remove('active');
            }});
            event.target.classList.add('active');
            renderCards();
        }}

        function handleSearch() {{
            searchQuery = document.getElementById('searchInput').value;
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

        renderCards();
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
