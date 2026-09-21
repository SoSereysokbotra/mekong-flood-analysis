"""Data discovery for the project: one place that knows where every input lives.

Everything here is read-only metadata lookup. Downloading / windowing happens in
`mfi.io`. Keeping the two apart means a notebook can list scenes without touching
disk, and the same query is reused by Level 4 and Level 6.
"""
from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass
from datetime import date

import planetary_computer as pc
import pystac_client

PC_STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
AOI_FILE = DATA / "aoi" / "banteay_meanchey_adm1.geojson"

# Anchor event: Oct 2020 Cambodia floods. Two tracks cover 100% of Banteay
# Meanchey: 164 descending (one slice per date, passes on the 14 Oct peak) and
# 99 ascending (Oct 4/10/16/22). Track 164 is the default; 99 is the second,
# independent viewing geometry for held-out checks. (Rel. orbit 26, the
# Sen1Floods11 Cambodia track, does not touch this province.)
ANCHOR_REL_ORBIT = 164
ANCHOR_ORBIT_STATE = "descending"
SECOND_REL_ORBIT = 99
SECOND_ORBIT_STATE = "ascending"


def aoi_geometry() -> dict:
    """Banteay Meanchey province polygon (GeoJSON geometry, EPSG:4326)."""
    with open(AOI_FILE, encoding="utf-8") as f:
        return json.load(f)["features"][0]["geometry"]


def aoi_bbox() -> list[float]:
    geom = aoi_geometry()

    def walk(c):
        if isinstance(c[0], (int, float)):
            yield c
        else:
            for x in c:
                yield from walk(x)

    pts = list(walk(geom["coordinates"]))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return [min(xs), min(ys), max(xs), max(ys)]


def _client() -> pystac_client.Client:
    return pystac_client.Client.open(PC_STAC, modifier=pc.sign_inplace)


@dataclass(frozen=True)
class Scene:
    id: str
    date: date
    orbit_state: str
    rel_orbit: int
    platform: str
    href_vv: str
    href_vh: str
    epsg: int

    @classmethod
    def from_item(cls, item) -> "Scene":
        p = item.properties
        return cls(
            id=item.id,
            date=item.datetime.date(),
            orbit_state=p["sat:orbit_state"],
            rel_orbit=int(p["sat:relative_orbit"]),
            platform=p.get("platform", ""),
            href_vv=item.assets["vv"].href,
            href_vh=item.assets["vh"].href,
            epsg=_epsg(p),
        )


def _epsg(props: dict) -> int:
    """Items carry either the old 'proj:epsg' or the newer 'proj:code' ('EPSG:32648')."""
    if "proj:epsg" in props:
        return int(props["proj:epsg"])
    code = props.get("proj:code", "")
    if code.upper().startswith("EPSG:"):
        return int(code.split(":")[1])
    return 0


def s1_rtc_scenes(
    start: str,
    end: str,
    *,
    rel_orbit: int | None = ANCHOR_REL_ORBIT,
    orbit_state: str | None = ANCHOR_ORBIT_STATE,
    intersects: dict | None = None,
) -> list[Scene]:
    """Sentinel-1 RTC scenes over the AOI between two ISO dates (inclusive).

    Defaults to the anchor track (rel. orbit 164 descending). Pass
    ``rel_orbit=None, orbit_state=None`` to get every track.
    Hrefs are signed and valid for roughly an hour; re-query rather than cache.
    """
    query = {}
    if rel_orbit is not None:
        query["sat:relative_orbit"] = {"eq": rel_orbit}
    if orbit_state is not None:
        query["sat:orbit_state"] = {"eq": orbit_state}
    search = _client().search(
        collections=["sentinel-1-rtc"],
        intersects=intersects or aoi_geometry(),
        datetime=f"{start}/{end}",
        query=query or None,
    )
    scenes = [Scene.from_item(i) for i in search.items()]
    return sorted(scenes, key=lambda s: (s.date, s.id))


def worldcover_items(year: int = 2020):
    """ESA WorldCover tiles over the AOI. 2020 = v1.0 (matches anchor year)."""
    return list(
        _client()
        .search(
            collections=["esa-worldcover"],
            intersects=aoi_geometry(),
            datetime=f"{year}-01-01/{year}-12-31",
        )
        .items()
    )


def jrc_gsw_items():
    """JRC Global Surface Water tiles (1984-2020 edition) over the AOI."""
    return list(_client().search(collections=["jrc-gsw"], intersects=aoi_geometry()).items())


def dem_items():
    """Copernicus DEM GLO-30 tiles over the AOI."""
    return list(_client().search(collections=["cop-dem-glo-30"], intersects=aoi_geometry()).items())


# --- Sen1Floods11 -----------------------------------------------------------

S1F11 = DATA / "raw" / "sen1floods11"
S1F11_HAND = S1F11 / "data" / "flood_events" / "HandLabeled"
S1F11_WEAK = S1F11 / "data" / "flood_events" / "WeaklyLabeled"

# Events whose hand-labelled chips are held out entirely (rule 8, no leakage).
HELD_OUT_EVENTS = ("Mekong",)


def s1f11_hand_chips() -> list[str]:
    """Chip ids like 'Mekong_123456' for every hand-labelled chip on disk."""
    return sorted(p.stem.removesuffix("_S1Hand") for p in (S1F11_HAND / "S1Hand").glob("*_S1Hand.tif"))


def s1f11_event(chip_id: str) -> str:
    return chip_id.split("_")[0]


def s1f11_paths(chip_id: str) -> dict[str, pathlib.Path]:
    """All layers for one chip. Only LabelHand is a valid evaluation label."""
    return {
        "s1": S1F11_HAND / "S1Hand" / f"{chip_id}_S1Hand.tif",
        "s2": S1F11_HAND / "S2Hand" / f"{chip_id}_S2Hand.tif",
        "label": S1F11_HAND / "LabelHand" / f"{chip_id}_LabelHand.tif",
        "otsu": S1F11_HAND / "S1OtsuLabelHand" / f"{chip_id}_S1OtsuLabelHand.tif",
        "jrc": S1F11_HAND / "JRCWaterHand" / f"{chip_id}_JRCWaterHand.tif",
    }


def s1f11_split() -> dict[str, list[str]]:
    """Project split, by event, not by random chip.

    - test:  every chip from HELD_OUT_EVENTS (Cambodia)
    - valid: the official valid+test chips of the remaining events
    - train: the official train chips of the remaining events (+ Bolivia)
    The official CSVs are only used to keep a valid/train partition within
    non-held-out events; they never decide what goes into test.
    """
    splits_dir = S1F11 / "splits" / "flood_handlabeled"

    def read(name):
        with open(splits_dir / f"flood_{name}_data.csv") as f:
            return [line.split(",")[0].removesuffix("_S1Hand.tif") for line in f.read().split() if line]

    official = {k: read(k) for k in ("train", "valid", "test", "bolivia")}
    out = {"train": [], "valid": [], "test": []}
    for name, chips in official.items():
        for c in chips:
            if s1f11_event(c) in HELD_OUT_EVENTS:
                out["test"].append(c)
            elif name in ("valid", "test"):
                out["valid"].append(c)
            else:
                out["train"].append(c)
    return {k: sorted(v) for k, v in out.items()}


def s1f11_weak_chips() -> list[str]:
    """Weakly-labelled chip ids on disk, with held-out events removed.

    This is the only sanctioned way to list weak chips: it guarantees the model
    never sees Cambodian imagery before test time, even via weak labels.
    Weak labels are for optional training experiments only, never evaluation.
    """
    chips = sorted(p.stem.removesuffix("_S1Weak") for p in (S1F11_WEAK / "S1Weak").glob("*_S1Weak.tif"))
    return [c for c in chips if s1f11_event(c) not in HELD_OUT_EVENTS]
