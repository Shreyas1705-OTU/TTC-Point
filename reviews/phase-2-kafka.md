# Phase 2 Review — Kafka

## Goal
Decouple *producing* vehicle positions (the Python poller) from
*consuming* them (Logstash, in Phase 3): the poller shouldn't need to
know or care who reads its data, and a consumer should be able to
restart without losing in-flight messages. This is the core "distributed
streaming" pattern the whole project demonstrates.

## Decisions made
- **KRaft mode, single broker.** Kafka 4.x removed ZooKeeper support
  entirely, so KRaft (Kafka's self-managed metadata mode) is the only
  option anyway, and it means one fewer container to run. Single broker
  is enough — this project demonstrates the pattern, not throughput.
- **Two listeners, deliberately.** `PLAINTEXT` (advertised as
  `localhost:9092`) is for the host — our Python producer runs outside
  Docker until Phase 5. `INTERNAL` (advertised as `kafka:29092`) is for
  other containers on the same Docker network — Logstash will use this
  in Phase 3. Kafka has to advertise a different address to each
  audience because "localhost" means something different from inside a
  container vs. from the host.
- **confluent-kafka over kafka-python** for the producer client — it's
  actively maintained (backed by librdkafka) and matches what you'd
  actually use in a real deployment, vs. kafka-python which lags newer
  broker protocol versions.
- **Messages keyed by `vehicle_id`.** Kafka only guarantees ordering
  within a partition, not across the whole topic. Keying by vehicle_id
  means every update for one vehicle always lands on the same partition,
  so a stale position can never arrive after a newer one for that
  vehicle just because of partition assignment.
- **3 partitions, replication factor 1.** Multiple partitions to
  actually demonstrate partitioning/keyed-ordering; replication factor 1
  because there's only one broker.

## What was built
- `docker-compose.yml` — Kafka (`apache/kafka:latest`, image resolved to
  Kafka 4.3.1) in KRaft combined mode (broker+controller), with a
  healthcheck via `kafka-broker-api-versions.sh`.
- `vehicle-positions` topic created (3 partitions, replication factor 1).
- `ingestion/ttc_producer.py` extended: `publish()` now sends each
  decoded record to Kafka via `confluent_kafka.Producer`, JSON-encoded,
  keyed by vehicle_id; `main()` polls, publishes, and flushes every 20s.

## Verification (actual results)
- `docker inspect` showed the Kafka container reach `healthy` status
  after fixing the healthcheck to use the script's full path
  (`/opt/kafka/bin/kafka-broker-api-versions.sh` - not on `PATH` by
  default in this image).
- One live fetch+publish cycle: **1857 records fetched and published**
  without error.
- `kafka-console-consumer --from-beginning` against the topic read real
  messages back, e.g.
  `{"vehicle_id": "3633", "route_id": "927", "trip_id": "75234020", "lat": 43.6376, "lon": -79.5358, ...}`
  — confirms data actually round-trips through Kafka, not just that
  `producer.flush()` didn't throw.

## Outcome
Kafka is up, healthy, and proven to carry real TTC data end-to-end from
the producer to a consumer. Safe to build Logstash's Kafka input on top
of this in Phase 3.

## Next phase
Phase 3 — Logstash consumes from the `INTERNAL` listener, enriches each
record via the `translate` filter against `data/lookups/routes.csv`,
reshapes lat/lon into a `geo_point`, and indexes into Elasticsearch.
