"""Turn static GTFS routes.txt into lookups for Logstash's translate filter.

Lets Logstash turn a bare route_id like "504" into "504" (King) with the
right streetcar color, without Logstash itself needing any GTFS knowledge.

`routes.csv` is the human-readable combined view. Logstash's `translate`
filter maps one key to exactly one value though, so route_short_name.yml/
route_color.yml/route_type.yml are the same data split into single
key->value dictionaries - one per field Logstash needs to enrich.
"""
import csv
from pathlib import Path

import yaml

STATIC_DIR = Path(__file__).resolve().parent.parent / "data" / "static"
LOOKUPS_DIR = Path(__file__).resolve().parent.parent / "data" / "lookups"

# GTFS route_type codes: https://gtfs.org/documentation/schedule/reference/#routestxt
# Only 0 (streetcar) and 3 (bus) are relevant - this feed is surface-only.
ROUTE_TYPE_LABELS = {
    "0": "streetcar",
    "3": "bus",
}


def main():
    routes_txt = STATIC_DIR / "routes.txt"
    if not routes_txt.exists():
        raise SystemExit(f"{routes_txt} not found - run fetch_static_gtfs.py first")

    LOOKUPS_DIR.mkdir(parents=True, exist_ok=True)

    short_names, colors, types = {}, {}, {}
    with routes_txt.open(newline="", encoding="utf-8-sig") as src:
        reader = csv.DictReader(src)
        rows = list(reader)

    for row in rows:
        route_id = row["route_id"]
        short_names[route_id] = row["route_short_name"] or route_id
        colors[route_id] = row.get("route_color") or "unknown"
        types[route_id] = ROUTE_TYPE_LABELS.get(row["route_type"], row["route_type"])

    with (LOOKUPS_DIR / "routes.csv").open("w", newline="", encoding="utf-8") as dst:
        writer = csv.writer(dst)
        writer.writerow(["route_id", "route_short_name", "route_color", "route_type"])
        for route_id in short_names:
            writer.writerow([route_id, short_names[route_id], colors[route_id], types[route_id]])

    for name, mapping in [
        ("route_short_name.yml", short_names),
        ("route_color.yml", colors),
        ("route_type.yml", types),
    ]:
        with (LOOKUPS_DIR / name).open("w", encoding="utf-8") as f:
            yaml.safe_dump(mapping, f, default_flow_style=False)

    print(f"Wrote {len(short_names)} routes to {LOOKUPS_DIR}")


if __name__ == "__main__":
    main()
