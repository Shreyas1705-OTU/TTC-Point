"""Poll TTC's GTFS-realtime vehicle-positions feed and publish decoded
records to Kafka.

Kafka decouples producing (this poller) from consuming (Logstash, from
Phase 3): neither side needs to know about the other, and Kafka durably
holds messages in the topic until a consumer reads them, so a consumer can
be stopped and restarted without losing in-flight data.
"""
import json
import sys
import time

import requests
from confluent_kafka import Producer
from google.transit import gtfs_realtime_pb2

VEHICLE_POSITIONS_URL = "https://bustime.ttc.ca/gtfsrt/vehicles"
POLL_INTERVAL_SECONDS = 20
KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
KAFKA_TOPIC = "vehicle-positions"


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


def publish(producer: Producer, records: list[dict]) -> None:
    # Key each message by vehicle_id so all updates for one vehicle land on
    # the same partition - Kafka only guarantees ordering within a
    # partition, and we don't want a stale position for a vehicle arriving
    # after a newer one just because they landed on different partitions.
    for record in records:
        producer.produce(
            KAFKA_TOPIC,
            key=record["vehicle_id"].encode("utf-8"),
            value=json.dumps(record).encode("utf-8"),
        )
    producer.flush()


def main():
    producer = Producer({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})
    print(
        f"Polling {VEHICLE_POSITIONS_URL} every {POLL_INTERVAL_SECONDS}s, "
        f"publishing to Kafka topic '{KAFKA_TOPIC}'. Ctrl+C to stop."
    )
    while True:
        try:
            records = fetch_vehicle_positions()
            publish(producer, records)
        except requests.RequestException as exc:
            print(f"fetch failed: {exc}", file=sys.stderr)
        else:
            print(f"published {len(records)} vehicle positions")
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
