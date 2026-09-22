"""Raster reading and windowing. Every array leaving this module has a known
unit and a known grid, so downstream code never has to guess.

Conventions:
- Sentinel-1 arrays are float32 in dB, shape (2, H, W) = (VV, VH).
- Labels are int8: 1 = water, 0 = no water, -1 = no data / uncertain.
- Ancillary rasters (WorldCover, JRC, DEM) are returned on the *target* grid
  (the chip or scene they are being paired with), resampled with nearest
  neighbour for categorical layers and bilinear for continuous ones.
"""
from __future__ import annotations

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT

from . import catalog

DB_FLOOR = -50.0  # gamma-nought below this is treated as no signal (zero power)


def to_db(power: np.ndarray) -> np.ndarray:
    """Linear power -> dB. Zero power floors at DB_FLOOR; NaN (nodata) stays NaN.

    Nodata must not become a very dark pixel: a dark pixel is what a flood
    detector looks for, so RTC scene collars would otherwise be "flooded".
    """
    p = np.asarray(power, dtype=np.float32)
    nodata = np.isnan(p)
    with np.errstate(divide="ignore", invalid="ignore"):
        db = 10.0 * np.log10(p)
    db = np.where(np.isfinite(db), db, DB_FLOOR).clip(min=DB_FLOOR).astype(np.float32)
    db[nodata] = np.nan
    return db


class Grid:
    """The spatial reference of an array: CRS + affine transform + shape."""

    def __init__(self, crs, transform, height, width):
        self.crs, self.transform, self.height, self.width = crs, transform, height, width

    @classmethod
    def of(cls, src: rasterio.DatasetReader) -> "Grid":
        return cls(src.crs, src.transform, src.height, src.width)

    @property
    def bounds(self):
        return rasterio.transform.array_bounds(self.height, self.width, self.transform)


# --- Sen1Floods11 chips -----------------------------------------------------

def read_s1f11_chip(chip_id: str) -> tuple[np.ndarray, np.ndarray, Grid]:
    """(s1_db[2,H,W], label[H,W], grid) for a hand-labelled chip.

    Sen1Floods11 S1 chips are already in dB (GEE COPERNICUS/S1_GRD export),
    so no conversion is applied here. NaNs in S1 are mapped to DB_FLOOR and the
    corresponding label pixels are set to -1 so they are excluded from scoring.
    """
    paths = catalog.s1f11_paths(chip_id)
    with rasterio.open(paths["s1"]) as src:
        s1 = src.read().astype(np.float32)
        grid = Grid.of(src)
    with rasterio.open(paths["label"]) as src:
        label = src.read(1).astype(np.int8)
    bad = ~np.isfinite(s1).all(axis=0)
    s1[:, bad] = DB_FLOOR
    label[bad] = -1
    return s1, label, grid


def read_s1f11_layer(chip_id: str, layer: str) -> np.ndarray:
    """One of 'otsu', 'jrc' (int8) for a chip. Never use these as labels."""
    if layer not in ("otsu", "jrc"):
        raise ValueError(f"layer must be 'otsu' or 'jrc', not {layer!r}; use read_s1f11_s2 for optical")
    with rasterio.open(catalog.s1f11_paths(chip_id)[layer]) as src:
        return src.read(1).astype(np.int8)


def read_s1f11_s2(chip_id: str) -> np.ndarray:
    """Sentinel-2 L1C reflectance chip, uint16 (13, H, W). Visual checks only."""
    with rasterio.open(catalog.s1f11_paths(chip_id)["s2"]) as src:
        return src.read()


def worldcover_chip(chip_id: str, grid: Grid | None = None) -> np.ndarray:
    """ESA WorldCover 2020 on a Sen1Floods11 chip grid, cached under data/interim.

    Fetches from Planetary Computer on first use; afterwards reads the cached
    GeoTIFF so every level uses the identical land-cover raster per chip.
    """
    p = catalog.DATA / "interim" / "worldcover_chips" / f"{chip_id}_WorldCover2020.tif"
    if p.exists():
        with rasterio.open(p) as src:
            return src.read(1)
    if grid is None:
        with rasterio.open(catalog.s1f11_paths(chip_id)["s1"]) as src:
            grid = Grid.of(src)
    wc = worldcover_on_grid(grid, year=2020)
    p.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        p, "w", driver="GTiff", height=grid.height, width=grid.width, count=1, dtype="uint8",
        crs=grid.crs, transform=grid.transform, compress="deflate", nodata=0,
    ) as dst:
        dst.write(wc, 1)
    return wc


def dem_chip(chip_id: str, grid: Grid | None = None, items=None) -> np.ndarray:
    """Copernicus DEM GLO-30 (m, float32) on a Sen1Floods11 chip grid, cached like worldcover_chip.

    `items`: optional pre-fetched STAC items covering the chip (one search per
    event instead of one per chip keeps the STAC API happy).
    """
    p = catalog.DATA / "interim" / "dem_chips" / f"{chip_id}_CopDEM30.tif"
    if p.exists():
        with rasterio.open(p) as src:
            return src.read(1)
    if grid is None:
        with rasterio.open(catalog.s1f11_paths(chip_id)["s1"]) as src:
            grid = Grid.of(src)
    dem = dem_on_grid(grid, items=items)
    p.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        p, "w", driver="GTiff", height=grid.height, width=grid.width, count=1, dtype="float32",
        crs=grid.crs, transform=grid.transform, compress="deflate", nodata=np.nan,
    ) as dst:
        dst.write(dem, 1)
    return dem


def slope_deg(dem: np.ndarray, grid: Grid) -> np.ndarray:
    """Slope in degrees from a DEM on `grid`.

    Chip grids are geographic (EPSG:4326), so pixel spacing is in degrees and
    must be converted to metres before differencing: 1 deg lat ~ 111,320 m,
    1 deg lon ~ 111,320 * cos(lat) m. Projected grids use their native spacing.
    """
    t = grid.transform
    if grid.crs and grid.crs.is_geographic:
        lat = t.f + t.e * grid.height / 2  # centre latitude (e is negative for north-up)
        dy = abs(t.e) * 111_320.0
        dx = abs(t.a) * 111_320.0 * np.cos(np.deg2rad(lat))
    else:
        dx, dy = abs(t.a), abs(t.e)
    gy, gx = np.gradient(dem.astype(np.float32), dy, dx)
    return np.degrees(np.arctan(np.hypot(gx, gy))).astype(np.float32)


# --- Ancillary rasters resampled onto a target grid -------------------------

def _read_on_grid(href: str, grid: Grid, resampling: Resampling) -> tuple[np.ndarray, np.ndarray]:
    """(values, valid_mask) of band 1 warped onto `grid`.

    The mask comes from the VRT itself, so it is right for every nodata
    convention: explicit nodata value, NaN, alpha band, or plain out-of-extent.

    A float source with no declared nodata (Copernicus DEM on Planetary
    Computer) is given NaN as nodata; otherwise GDAL cannot mark out-of-extent
    pixels and the VRT reports the whole grid as valid, filled with 0.
    """
    with rasterio.open(href) as src:
        nodata = src.nodata
        if nodata is None and np.issubdtype(np.dtype(src.dtypes[0]), np.floating):
            nodata = float("nan")
        with WarpedVRT(
            src,
            crs=grid.crs,
            transform=grid.transform,
            width=grid.width,
            height=grid.height,
            resampling=resampling,
            nodata=nodata,
        ) as vrt:
            return vrt.read(1), vrt.read_masks(1) > 0


def _items_covering(items, grid: Grid):
    """Filter STAC items to those whose bbox intersects the grid (in EPSG:4326)."""
    from rasterio.warp import transform_bounds

    l, b, r, t = transform_bounds(grid.crs, "EPSG:4326", *grid.bounds)
    out = []
    for it in items:
        il, ib, ir, it_ = it.bbox
        if not (ir < l or il > r or it_ < b or ib > t):
            out.append(it)
    return out


def _mosaic_on_grid(items, asset: str, grid: Grid, resampling: Resampling, fill) -> np.ndarray:
    """Read one asset from every covering item and mosaic (first valid wins)."""
    out = None
    for it in _items_covering(items, grid):
        arr, valid = _read_on_grid(it.assets[asset].href, grid, resampling)
        if out is None:
            out = np.full(arr.shape, fill, dtype=arr.dtype)
            filled = np.zeros(arr.shape, bool)
        take = valid & ~filled
        out[take] = arr[take]
        filled |= take
    if out is None:
        raise ValueError("no items cover this grid")
    return out


def worldcover_on_grid(grid: Grid, year: int = 2020) -> np.ndarray:
    """ESA WorldCover class codes (uint8) resampled nearest onto `grid`.

    Searches globally for the grid's footprint, not just the Cambodia AOI, so it
    works for every Sen1Floods11 event.
    """
    from rasterio.warp import transform_bounds

    bbox = list(transform_bounds(grid.crs, "EPSG:4326", *grid.bounds))
    items = list(
        catalog._client()
        .search(collections=["esa-worldcover"], bbox=bbox, datetime=f"{year}-01-01/{year}-12-31")
        .items()
    )
    return _mosaic_on_grid(items, "map", grid, Resampling.nearest, fill=0).astype(np.uint8)


def jrc_occurrence_on_grid(grid: Grid) -> np.ndarray:
    """JRC GSW water occurrence (% of valid observations, 0-100), nearest."""
    from rasterio.warp import transform_bounds

    bbox = list(transform_bounds(grid.crs, "EPSG:4326", *grid.bounds))
    items = list(catalog._client().search(collections=["jrc-gsw"], bbox=bbox).items())
    return _mosaic_on_grid(items, "occurrence", grid, Resampling.nearest, fill=0).astype(np.uint8)


def dem_on_grid(grid: Grid, items=None) -> np.ndarray:
    """Copernicus DEM GLO-30 elevation (m), bilinear onto `grid`. `items` may be pre-fetched."""
    from rasterio.warp import transform_bounds

    if items is None:
        bbox = list(transform_bounds(grid.crs, "EPSG:4326", *grid.bounds))
        items = list(catalog._client().search(collections=["cop-dem-glo-30"], bbox=bbox).items())
    return _mosaic_on_grid(items, "data", grid, Resampling.bilinear, fill=np.nan).astype(np.float32)
