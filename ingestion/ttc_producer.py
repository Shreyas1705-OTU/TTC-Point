"""Poll TTC's GTFS-realtime vehicle-positions feed and print decoded records.

Phase 1: prove we can read TTC's live data at all before Kafka enters the
picture. Kafka publishing is added in Phase 2.
"""
import sys
import time

import requests
from google.transit import gtfs_realtime_pb2

VEHICLE_POSITIONS_URL = "https://bustime.ttc.ca/gtfsrt/vehicles"
POLL_INTERVAL_SECONDS = 20


def fetch_vehicle_positions(url: str = VEHICLE_POSITIONS_URL) -> list[dict]:
    response = requests.get(url, timeout=10)
    response.raise_for_status()

    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(response.content)

    records = []
    for entity in feed.entity:
        if not entity.HasField("vehicle"):
            continue
        vp = entity.vehicle
        records.append(
            {
                "vehicle_id": vp.vehicle.id,
                "route_id": vp.trip.route_id,
                "trip_id": vp.trip.trip_id,
                "lat": vp.position.latitude,
                "lon": vp.position.longitude,
                "bearing": vp.position.bearing,
                "speed": vp.position.speed,
                "timestamp": vp.timestamp or feed.header.timestamp,
            }
        )
    return records


def main():
    print(f"Polling {VEHICLE_POSITIONS_URL} every {POLL_INTERVAL_SECONDS}s. Ctrl+C to stop.")
    while True:
        try:
            records = fetch_vehicle_positions()
        except requests.RequestException as exc:
            print(f"fetch failed: {exc}", file=sys.stderr)
        else:
            print(f"--- {len(records)} vehicles ---")
            for record in records:
                print(record)
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
