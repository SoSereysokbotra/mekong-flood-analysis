"""Download the Sen1Floods11 v1.1 hand-labelled subset from the public GCS bucket.

Only the HandLabeled folders are fetched by default (~735 MB). The WeaklyLabeled
set (~7.3 GB, radar-Otsu / S2-index generated labels) is opt-in via --weak,
because those labels carry the "dark = water" bias this project studies and
must never be used for evaluation.

Usage:
    python scripts/download_sen1floods11.py            # hand-labelled only
    python scripts/download_sen1floods11.py --weak     # also weak-labelled
"""
import argparse
import concurrent.futures as cf
import pathlib
import sys

import requests

BUCKET = "sen1floods11"
LIST_URL = f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/o"
GET_URL = f"https://storage.googleapis.com/{BUCKET}/"
OUT = pathlib.Path(__file__).resolve().parents[1] / "data" / "raw" / "sen1floods11"

HAND = [
    "v1.1/data/flood_events/HandLabeled/S1Hand/",
    "v1.1/data/flood_events/HandLabeled/LabelHand/",
    "v1.1/data/flood_events/HandLabeled/S1OtsuLabelHand/",
    "v1.1/data/flood_events/HandLabeled/JRCWaterHand/",
    "v1.1/data/flood_events/HandLabeled/S2Hand/",
]
WEAK = [
    "v1.1/data/flood_events/WeaklyLabeled/S1Weak/",
    "v1.1/data/flood_events/WeaklyLabeled/S1OtsuLabelWeak/",
    "v1.1/data/flood_events/WeaklyLabeled/S2IndexLabelWeak/",
]


def list_objects(prefix):
    names, token = [], None
    while True:
        params = {"prefix": prefix, "maxResults": 1000}
        if token:
            params["pageToken"] = token
        j = requests.get(LIST_URL, params=params, timeout=60).json()
        names += [(i["name"], int(i.get("size", 0))) for i in j.get("items", [])]
        token = j.get("nextPageToken")
        if not token:
            return names


def fetch(name, size):
    dest = OUT / name.removeprefix("v1.1/")
    if dest.exists() and dest.stat().st_size == size:
        return 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(GET_URL + name, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    return size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weak", action="store_true", help="also fetch the weakly-labelled set (~7.3 GB)")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    prefixes = HAND + (WEAK if args.weak else [])
    objs = []
    for p in prefixes:
        got = list_objects(p)
        print(f"{p}: {len(got)} files, {sum(s for _, s in got) / 1e6:.0f} MB", flush=True)
        objs += got

    done = 0
    with cf.ThreadPoolExecutor(args.workers) as ex:
        for i, n in enumerate(ex.map(lambda o: fetch(*o), objs), 1):
            done += n
            if i % 100 == 0 or i == len(objs):
                print(f"  {i}/{len(objs)} files, {done / 1e6:.0f} MB new", flush=True)
    print("done ->", OUT)


if __name__ == "__main__":
    sys.exit(main())
