# Phase 1 Review — Prove the Data Source

## Goal
Confirm TTC's live GTFS-realtime feed and static GTFS dataset are readable
and joinable, before building anything on top of them (Kafka, Logstash,
Elasticsearch, Kibana).

## Decisions made
- **Scope: bus + streetcar only, no subway.** TTC's `bustime.ttc.ca`
  feeds are surface-only (confirmed via Transitland as
  `f-dpz8-ttc~surface~rt`); TTC does not publish live GPS vehicle positions
  for subway (signal-based, not GPS-tracked). Confirmed with user: no live
  dots for subway means no point including it at all — not even as a
  static line overlay.
- **Confirmed feed URLs** (verified live):
  - Vehicle Positions: `https://bustime.ttc.ca/gtfsrt/vehicles`
  - Trip Updates: `https://bustime.ttc.ca/gtfsrt/trips`
  - Service Alerts: `https://bustime.ttc.ca/gtfsrt/alerts`
- **Static GTFS resolved dynamically** via Toronto's CKAN API
  (`package_show?id=ttc-routes-and-schedules`), with a hardcoded fallback
  URL, since CKAN resource IDs rotate roughly every 6 weeks when TTC
  republishes the dataset.

## What was built
- `ingestion/ttc_producer.py` — polls the vehicle-positions feed, decodes
  protobuf via `gtfs-realtime-bindings`, extracts vehicle_id, route_id,
  trip_id, lat, lon, bearing, speed, timestamp. `main()` loops on a 20s
  interval; Kafka publishing comes in Phase 2.
- `ingestion/fetch_static_gtfs.py` — downloads and extracts TTC's static
  surface GTFS zip.
- `ingestion/build_route_lookup.py` — turns `routes.txt` into
  `data/lookups/routes.csv` (route_id → short_name, color, bus/streetcar
  type) for Logstash's translate filter in Phase 3.

## Verification (actual results)
- Live feed pull: **1853 real vehicles** decoded successfully, e.g.
  `{'vehicle_id': '3638', 'route_id': '96', 'trip_id': '56815020', 'lat': 43.7447, 'lon': -79.4051, 'bearing': 266.0, 'speed': 0.0, ...}`
  — coordinates fall inside Toronto's bounding box.
- Static GTFS extracted successfully: `routes.txt`, `stops.txt`,
  `trips.txt`, `shapes.txt`, etc. present.
- Route lookup built: **230 routes** written to `data/lookups/routes.csv`.
- Cross-check: live route IDs `96, 84, 52, 952` and known streetcar routes
  `501, 504, 505, 506, 510` all resolve correctly in the lookup, with
  correct bus/streetcar classification (17 streetcar routes found total).

## Outcome
Data source is proven end-to-end: real, live, decodable, and joinable to
human-readable route info. Safe to build Kafka on top of this in Phase 2.

## Next phase
Phase 2 — add Kafka (KRaft, single broker), publish decoded records to a
`vehicle-positions` topic, verify with a console consumer.
