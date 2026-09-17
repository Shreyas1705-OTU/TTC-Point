# Phase 3 Review — Logstash + Elasticsearch

## Goal
Turn raw Kafka messages into enriched, queryable documents. Logstash is
the "T" in an ETL-shaped pipeline: it joins in data the feed itself
doesn't carry (route name/color, since GTFS-RT only has a bare
route_id), and reshapes fields into what Elasticsearch needs (a real
`geo_point`, a proper `@timestamp`). Elasticsearch is the store that
lets Kibana ask "what's near this map viewport right now," fast, over a
constantly-growing stream.

## Decisions made
- **Elastic Stack 9.5.4** for Elasticsearch, Logstash, and Kibana (current
  stable as of this build) - kept all three on the same version, which
  the Elastic Stack expects.
- **Security disabled** (`xpack.security.enabled=false` on both
  Elasticsearch and Kibana). This is a local demo stack, not a
  production deployment - cert/password setup would add real friction
  for zero benefit here.
- **translate filter needs one dictionary per field.** Logstash's
  `translate` filter maps exactly one key to one value, so
  `build_route_lookup.py` (from Phase 1) now also emits
  `route_short_name.yml`, `route_color.yml`, and `route_type.yml` as
  separate YAML dictionaries alongside the human-readable `routes.csv` -
  three `translate` filter instances in the pipeline, one per field.
- **Drop vehicles with no route_id.** ~40% of raw messages have an empty
  `route_id` (deadheading/out-of-service vehicles per the feed) - nothing
  useful to show or color on the map, so the pipeline drops them before
  they ever reach Elasticsearch.
- **Index template applied before first document.** Elasticsearch infers
  a mapping from whatever document arrives first; without a template,
  `location` would've been guessed as a plain object, not `geo_point`,
  and that's not fixable without reindexing. The template
  (`elasticsearch/templates/vehicle-positions-template.json`) is applied
  via `PUT _index_template` before Logstash ever writes anything.

## What was built
- `docker-compose.yml`: `elasticsearch` (single-node, `es-data` volume),
  `logstash` (mounts `logstash/pipeline/`, `logstash/config/logstash.yml`,
  and `data/lookups/` for the translate dictionaries), `kibana`.
- `logstash/pipeline/vehicle-positions.conf`: Kafka input (JSON codec,
  `kafka:29092` - the INTERNAL listener from Phase 2) -> drop
  empty-route_id events -> three `translate` filters (route enrichment)
  -> `mutate` to build `location.{lat,lon}` -> `date` filter (Unix
  timestamp -> `@timestamp`) -> Elasticsearch output.
- `ingestion/build_route_lookup.py` extended to also emit the three
  per-field YAML dictionaries Logstash needs.

## Bugs hit and fixed
- Kafka healthcheck script wasn't on `PATH` (fixed in Phase 2, still
  holding).
- Logstash 9.5.4 rejected `http.host` in `logstash.yml` - that setting
  was renamed to `api.http.host` in this version.
- Logstash's Kafka consumer starts from the *latest* offset by default,
  so it didn't see the Phase 2 test messages already sitting in the
  topic - had to publish a fresh batch after Logstash was up to see it
  flow through.

## Verification (actual results)
- `PUT _index_template/vehicle-positions-template` acknowledged; `GET
  _mapping` on the resulting index confirms `"location": {"type":
  "geo_point"}` - not a plain object.
- Ran the producer once against the live feed (1673 raw vehicles) with
  Logstash already consuming: **993 documents indexed** in
  `vehicle-positions` (the gap matches empty-route_id vehicles being
  dropped, as intended).
- Sample documents confirm real enrichment: route `504` and `501` came
  back tagged `route_type: streetcar`, `route_color: ed1c24`; route `113`
  came back `route_type: bus` - matching the static GTFS data joined in
  Phase 1.
- Kibana reachable and reporting `{"status":{"overall":{"level":
  "available"}}}` at `/api/status`.

## Outcome
Real TTC data now flows all the way from the live feed through Kafka,
through Logstash's enrichment, into Elasticsearch as correctly-typed,
human-readable documents. Safe to build the Kibana Map in Phase 4.

## Next phase
Phase 4 — the payoff: a Kibana Maps view over `vehicle-positions`,
colored by route_type, with auto-refresh so dots visibly move.
