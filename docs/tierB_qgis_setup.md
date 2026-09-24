# Tier B labelling — QGIS setup

Follow `data/labels/LABELLING_PROTOCOL.md` (frozen v1.0) for *what* to label. This is only *how* to set the software up.

Everything is already prepared:

| File | What it is |
| --- | --- |
| `data/labels/tierB_bmc_oct2020.gpkg` | layer `flood` — empty, draw into this; layer `tiles` — the 20 squares |
| `data/labels/labelling_log.csv` | one row per tile: fill in dates and minutes as you go |
| `results/level4/maps/*.tif` | the model outputs — **keep these switched off while labelling** |

## 1. Open the data

1. Open QGIS → **Project → New**
2. **Layer → Add Layer → Add Vector Layer** → select `data/labels/tierB_bmc_oct2020.gpkg` → add **both** layers (`tiles`, `flood`)
3. Set the project CRS to **EPSG:32648** (bottom-right of the window → search 32648)
4. Style `tiles`: right-click → Properties → Symbology → Simple fill → **Fill: no brush**, Stroke: red, width 0.6. Under **Labels**, choose Single labels on `tile_id`.
5. **Project → Save As** → `data/labels/tierB.qgz`

## 2. Add the imagery you label from

The protocol's evidence order is optical first, radar last. Add these as XYZ tiles: **Browser panel → XYZ Tiles → right-click → New Connection**

| Name | URL |
| --- | --- |
| Esri Satellite | `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}` |
| Google Satellite | `https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}` |

These are recent imagery, not October 2020 — they establish **land cover and field boundaries**, which is what step 2a of the protocol needs. For the event date itself use Sentinel-2 (below) and the elevation/hydrology reasoning.

**The event imagery is already downloaded**, in `data/labels/imagery/<tile_id>/optical/`:

| File | What it is |
| --- | --- |
| `pre_2020-09-25_clear*.tif` | before the flood — land cover, permanent water |
| `event_2020-10-15_clear*.tif` or `event_2020-10-20_...` | **the flood**, within a week of the radar date |
| `event_alt_*.tif` | a second event-window scene where one was usable |
| `post_2020-11-09_clear*.tif` | after — what drained |

`clear<pct>` in the filename is the measured clear fraction over *that tile*. `data/labels/optical_availability.csv` lists it for all 20. Three tiles (`BMC_CROP_04`, `BMC_CROP_08`, `BMC_CROP_14`) have almost no event-date optical — label what the pre/post pair and terrain support, and mark the rest `−1 uncertain`.

Drag the `optical/*.tif` files for your current tile straight into QGIS.

## 3. Draw

1. Zoom to a tile: open the `tiles` attribute table, sort by `label_order`, click row 1 (`BMC_CROP_01`), then **Zoom to selection**.
2. Select the `flood` layer → **Toggle Editing** (pencil icon) → **Add Polygon Feature**.
3. Draw the polygon, right-click to finish, then fill the attribute form:
   - `class`: 1 = flood open water, 2 = **flood with vegetation (the target class)**, 3 = permanent water, 0 = dry, −1 = uncertain
   - `confidence`: 3 = two sources agree, 2 = one clear source, 1 = weak
   - `evidence`: what you actually used, e.g. `S2 2020-10-30; DEM`
   - `labeller`: your name · `date_labelled`: today · `tile_id`: the tile you are in
4. Save edits often (Ctrl+S). Update `labelling_log.csv` when a tile is done.

You do **not** have to cover every pixel with polygons. Draw the water; anything not drawn inside a completed tile is treated as dry. Mark genuinely ambiguous areas as `−1 uncertain` rather than guessing — the protocol says to use it freely.

## 4. The one rule that matters most

Turn the radar on only at step 2d — to sharpen a boundary you already established from optical. If you draw water because the radar looks dark, the labels inherit exactly the bias this project exists to measure, and the test becomes worthless. In October the rice is 80–120 cm tall, so **flooded fields can look bright, like dry land**. That case is the whole point.

## 5. How long

20 tiles × 2 × 2 km. Expect 20–40 minutes per tile at first, less once you have the eye for it. It does not have to be one sitting — the log tracks where you stopped.
