"""Build a self-contained review page for the Tier B candidates.

QGIS digitising is the wrong tool for "is this shape water or not". This makes
one HTML file with a card per candidate: the event-date false-colour image with
the candidate outlined, the same patch before the flood, and three buttons.
Decisions are kept in the browser's local storage, so the review can be stopped
and resumed, and exported as a CSV that scripts/apply_review.py writes back
into the GeoPackage.

The page shows optical only. Radar is deliberately absent: the protocol puts it
last, and a labeller who sees the radar cannot un-see it.

Output: data/labels/review.html  (open it by double-clicking)
"""
from __future__ import annotations

import base64
import io as _io
import json
import pathlib
import sys

import geopandas as gpd
import numpy as np
import rasterio
from PIL import Image, ImageDraw
from rasterio.windows import from_bounds
from tqdm import tqdm

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog  # noqa: E402
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fetch_tier_b_imagery import OUT  # noqa: E402

GPKG = catalog.DATA / "labels" / "tierB_bmc_oct2020.gpkg"
PAGE = catalog.DATA / "labels" / "review.html"
PAD_M = 300.0        # context around the polygon
THUMB = 260          # px


def crop(path: pathlib.Path, bounds, poly=None) -> str | None:
    """Base64 PNG of the raster around `bounds`, with `poly` outlined."""
    if not path.exists():
        return None
    l, b, r, t = bounds
    with rasterio.open(path) as src:
        win = from_bounds(l - PAD_M, b - PAD_M, r + PAD_M, t + PAD_M, src.transform)
        win = win.intersection(rasterio.windows.Window(0, 0, src.width, src.height))
        if win.width < 2 or win.height < 2:
            return None
        arr = src.read(window=win, out_shape=(src.count, min(THUMB, int(win.height * 3)), min(THUMB, int(win.width * 3))),
                       resampling=rasterio.enums.Resampling.nearest)
        wt = rasterio.windows.transform(win, src.transform)
        sx = arr.shape[2] / win.width
        sy = arr.shape[1] / win.height
    if arr.shape[0] >= 3:
        img = Image.fromarray(np.transpose(arr[:3], (1, 2, 0)).astype(np.uint8))
    else:
        a = arr[0].astype(np.float32)
        a = np.clip((a + 0.4) / 0.8, 0, 1) * 255
        img = Image.fromarray(a.astype(np.uint8)).convert("RGB")
    img = img.resize((THUMB, THUMB), Image.NEAREST)
    if poly is not None:
        d = ImageDraw.Draw(img)
        fx = THUMB / (win.width * sx) * sx
        fy = THUMB / (win.height * sy) * sy
        for ring in ([poly.exterior] if poly.geom_type == "Polygon" else [g.exterior for g in poly.geoms]):
            pts = []
            for x, y in ring.coords:
                col, row = ~wt * (x, y)
                pts.append((col * fx, row * fy))
            if len(pts) > 2:
                d.line(pts + [pts[0]], fill=(255, 60, 60), width=3)
    buf = _io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def main():
    g = gpd.read_file(GPKG, layer="flood")
    water = g[g["evidence"].fillna("").str.contains("CANDIDATE")].copy()
    water = water.sort_values(["tile_id"]).reset_index()
    print(f"{len(water)} water candidates to review")

    cards = []
    for i, row in tqdm(water.iterrows(), total=len(water), desc="thumbnails"):
        tid = row["tile_id"]
        d = OUT / tid / "optical"
        ev = next(iter(sorted(d.glob("falsecolour_event_*.tif"))), None)
        pre = next(iter(sorted(d.glob("falsecolour_pre_*.tif"))), None)
        ndwi = next(iter(sorted(d.glob("ndwi_event_*.tif"))), None)
        b = row.geometry.bounds
        cards.append({
            "fid": int(row["index"]), "tile": tid, "class": int(row["class"]),
            "area_ha": round(row.geometry.area / 1e4, 2),
            "event": crop(ev, b, row.geometry), "pre": crop(pre, b, row.geometry),
            "ndwi": crop(ndwi, b, row.geometry),
            "event_name": ev.name if ev else "", "pre_name": pre.name if pre else "",
        })

    html = PAGE_TEMPLATE.replace("__CARDS__", json.dumps(cards))
    PAGE.write_text(html, encoding="utf-8")
    print(f"\nwrote {PAGE}  ({PAGE.stat().st_size / 1e6:.1f} MB)")
    print("Double-click it to open in your browser.")


PAGE_TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Tier B review</title>
<style>
:root{--bg:#14161a;--card:#1d2026;--ink:#e8eaed;--muted:#9aa0a6;--line:#2c3038;
      --yes:#2e7d32;--no:#c0392b;--maybe:#8a6d1f}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,Segoe UI,sans-serif}
header{position:sticky;top:0;background:#0f1114;border-bottom:1px solid var(--line);padding:10px 16px;z-index:5}
h1{font-size:16px;margin:0 0 4px}
#bar{height:6px;background:var(--line);border-radius:3px;overflow:hidden;margin-top:6px}
#fill{height:100%;background:#4c8dff;width:0}
.wrap{max-width:900px;margin:0 auto;padding:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;margin-bottom:14px}
.card.done{opacity:.45}
.imgs{display:flex;gap:10px;flex-wrap:wrap}
figure{margin:0}
figure img{display:block;border-radius:6px;border:1px solid var(--line);width:260px;height:260px;image-rendering:pixelated}
figcaption{font-size:12px;color:var(--muted);margin-top:4px;text-align:center}
.meta{font-size:13px;color:var(--muted);margin:8px 0}
.btns{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap}
button{border:0;border-radius:8px;padding:10px 16px;font-size:14px;font-weight:600;color:#fff;cursor:pointer}
.yes{background:var(--yes)} .no{background:var(--no)} .maybe{background:var(--maybe)}
button.sel{outline:3px solid #fff}
.ghost{background:#333;color:var(--ink)}
kbd{background:#2c3038;border-radius:4px;padding:1px 5px;font-size:11px}
#done{padding:20px;text-align:center;color:var(--muted)}
</style></head><body>
<header class="wrap" style="max-width:none">
  <h1>Tier B review — is the outlined area water on the flood date?</h1>
  <div class="meta" id="count"></div>
  <div id="bar"><div id="fill"></div></div>
  <div class="btns" style="margin-top:8px">
    <button class="ghost" onclick="exportCsv()">Download decisions (CSV)</button>
    <button class="ghost" onclick="if(confirm('Clear all decisions?')){localStorage.removeItem(KEY);render()}">Reset</button>
    <span class="meta">keys: <kbd>1</kbd> water · <kbd>2</kbd> not water · <kbd>3</kbd> unsure</span>
  </div>
</header>
<div class="wrap" id="list"></div>
<div id="done"></div>
<script>
const CARDS = __CARDS__;
const KEY = "tierb_review_v1";
let dec = JSON.parse(localStorage.getItem(KEY) || "{}");
let focus = 0;

function save(){ localStorage.setItem(KEY, JSON.stringify(dec)); }
function set(fid, v){ dec[fid]=v; save(); render(); }

function render(){
  const list = document.getElementById("list");
  list.innerHTML = "";
  CARDS.forEach((c,i)=>{
    const d = dec[c.fid];
    const el = document.createElement("div");
    el.className = "card" + (d ? " done":"");
    el.id = "c"+i;
    el.innerHTML = `
      <div class="meta"><b>${c.tile}</b> · ${c.area_ha} ha · candidate #${i+1} of ${CARDS.length}</div>
      <div class="imgs">
        ${c.event?`<figure><img src="data:image/png;base64,${c.event}"><figcaption>FLOOD DATE — water is dark blue/black</figcaption></figure>`:""}
        ${c.pre?`<figure><img src="data:image/png;base64,${c.pre}"><figcaption>BEFORE the flood</figcaption></figure>`:""}
        ${c.ndwi?`<figure><img src="data:image/png;base64,${c.ndwi}"><figcaption>water index (bright = wet)</figcaption></figure>`:""}
      </div>
      <div class="btns">
        <button class="yes${d==='water'?' sel':''}" onclick="set(${c.fid},'water')">Water</button>
        <button class="no${d==='not'?' sel':''}" onclick="set(${c.fid},'not')">Not water</button>
        <button class="maybe${d==='unsure'?' sel':''}" onclick="set(${c.fid},'unsure')">Unsure</button>
      </div>`;
    list.appendChild(el);
  });
  const n = Object.keys(dec).length;
  document.getElementById("count").textContent =
    `${n} of ${CARDS.length} reviewed — ${Object.values(dec).filter(v=>v==='water').length} water, ` +
    `${Object.values(dec).filter(v=>v==='not').length} not water, ${Object.values(dec).filter(v=>v==='unsure').length} unsure`;
  document.getElementById("fill").style.width = (100*n/CARDS.length)+"%";
  document.getElementById("done").textContent = n===CARDS.length ?
    "All reviewed — click Download decisions (CSV), then tell Claude where the file went." : "";
}

document.addEventListener("keydown", e=>{
  const map = {"1":"water","2":"not","3":"unsure"};
  if(!map[e.key]) return;
  while(focus < CARDS.length && dec[CARDS[focus].fid]) focus++;
  if(focus >= CARDS.length) return;
  set(CARDS[focus].fid, map[e.key]);
  const el = document.getElementById("c"+focus);
  if(el) el.scrollIntoView({block:"center"});
});

function exportCsv(){
  const rows = [["fid","tile_id","decision"]];
  CARDS.forEach(c=>{ if(dec[c.fid]) rows.push([c.fid, c.tile, dec[c.fid]]); });
  const blob = new Blob([rows.map(r=>r.join(",")).join("\n")], {type:"text/csv"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = "tierb_decisions.csv"; a.click();
}
render();
</script></body></html>
"""

if __name__ == "__main__":
    main()
