"""Turn static GTFS routes.txt into a flat lookup for Logstash's translate filter.

Lets Logstash turn a bare route_id like "504" into "504 King" with the
right streetcar color, without Logstash itself needing any GTFS knowledge.
"""
import csv
from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parent.parent / "data" / "static"
LOOKUP_PATH = Path(__file__).resolve().parent.parent / "data" / "lookups" / "routes.csv"

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

    LOOKUP_PATH.parent.mkdir(parents=True, exist_ok=True)
    with (
        routes_txt.open(newline="", encoding="utf-8-sig") as src,
        LOOKUP_PATH.open("w", newline="", encoding="utf-8") as dst,
    ):
        reader = csv.DictReader(src)
        writer = csv.writer(dst)
        writer.writerow(["route_id", "route_short_name", "route_color", "route_type"])
        count = 0
        for row in reader:
            route_type = ROUTE_TYPE_LABELS.get(row["route_type"], row["route_type"])
            writer.writerow(
                [
                    row["route_id"],
                    row["route_short_name"],
                    row.get("route_color", ""),
                    route_type,
                ]
            )
            count += 1
    print(f"Wrote {count} routes to {LOOKUP_PATH}")


if __name__ == "__main__":
    main()
