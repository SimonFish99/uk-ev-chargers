"""Group raw OpenChargeMap data into the per-town dataset the site build consumes.

Pipeline:  fetch_data.py  ->  prepare_data.py  ->  build_pages.py

Reads data/chargers.json (the raw OCM dump from fetch_data.py), groups charge
points by their town, keeps towns with at least MIN_CHARGERS public points, and
writes data/towns_filtered.json (consumed by build_pages.py).
"""
import json
from collections import defaultdict
from pathlib import Path

SRC = Path("data/chargers.json")
OUT = Path("data/towns_filtered.json")
MIN_CHARGERS = 5


def main():
    chargers = json.loads(SRC.read_text(encoding="utf-8"))
    groups = defaultdict(list)
    for c in chargers:
        town = ((c.get("AddressInfo") or {}).get("Town") or "").strip()
        if town:
            groups[town].append(c)
    filtered = {t: v for t, v in groups.items() if len(v) >= MIN_CHARGERS}
    OUT.write_text(json.dumps(filtered, ensure_ascii=False), encoding="utf-8")
    print(f"{len(chargers)} chargers -> {len(filtered)} towns with >= {MIN_CHARGERS} charge points")


if __name__ == "__main__":
    main()
