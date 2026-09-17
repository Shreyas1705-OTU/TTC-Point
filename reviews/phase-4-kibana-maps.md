# Phase 4 Review — Kibana Maps (the payoff)

## Goal
Turn the pipeline into the actual demo: a live map of Toronto with real
TTC vehicles visibly present, colored by type, refreshing on its own.
Everything before this phase was plumbing; this is where it becomes
something worth showing someone.

## Decisions made
- **Categorical color-by-value on `route_type`**, custom palette: bus =
  `#c51616` (red), streetcar = `#610dfb` (purple). Kibana's default
  categorical palette picked two similar shades of blue initially -
  not distinct enough for a demo, so colors were set explicitly per
  category instead of relying on the default palette.
- **2-minute time window, 15s auto-refresh** (not the 15-30s window
  originally planned). See "TTC's own lag" below - a window narrower
  than TTC's source-side latency shows nothing, so the window has to be
  wider than the real end-to-end lag, not just the poll interval.
- **Saved object edited before committing**: the raw Kibana export
  captured whatever transient time range/refresh state was on screen at
  export time (`now-47s`, refresh paused). Both were corrected in the
  exported `.ndjson` (`timeFilters` -> `now-2m`, `refreshConfig` ->
  `{isPaused: false, interval: 15000}`) so importing this saved object
  on a fresh stack (Phase 5) starts already demo-ready, not paused on a
  too-thin window.

## Real finding: TTC's own feed has ~24-47s of inherent lag
While debugging why a 15-second time window showed zero dots, measured
TTC's feed directly against wall-clock time:
- `feed.header.timestamp` (when TTC generated the feed snapshot) lags
  wall-clock by ~24s.
- Individual vehicle timestamps (when each vehicle's GPS last reported)
  lag wall-clock by a **median of ~46s**, max observed 491s (~8 min,
  likely one stale/dead GPS unit).

This lag originates entirely in TTC's own AVL/feed-generation
infrastructure, before our pipeline ever sees the data. Any dashboard
time window narrower than this will intermittently (or always) show
nothing - not because anything's broken, but because no document that
fresh exists yet. This is a general lesson for any near-real-time
pipeline: the display window must be wider than the actual end-to-end
latency of the whole chain, source included.

## What was built
- Kibana Maps: "TTC Live Bus and Streetcar Positions" - a Documents
  layer over the `vehicle-positions` data view, geo field `location`,
  styled by `route_type` with the custom red/purple palette above.
- `kibana/saved-objects/ttc-map-and-dashboards.ndjson` - exported data
  view + map (with related objects included, so the data view reference
  resolves on import without manual recreation).

## Verification (actual results)
- With the producer running continuously in the background and the map
  set to a 2-minute window, the map showed hundreds of live vehicles
  forming a clearly recognizable outline of Toronto's street grid -
  screenshot confirmed by the user directly from their browser.
- Confirmed via direct Elasticsearch queries during debugging: 12,549
  documents indexed in a trailing 5-minute window, all with valid
  `geo_point` locations and correct route enrichment.
- Bus vs. streetcar coloring confirmed visually distinct (red vs.
  purple) after fixing the initial default palette.

## Outcome
The actual demo artifact exists and works: a live, moving, correctly
colored map of Toronto transit, built entirely from real TTC data. Safe
to move to containerizing everything and writing deploy scripts.

## Next phase
Phase 5 — finalize `docker-compose.yml` end-to-end (including the
producer itself), add Kubernetes manifests (Kind cluster pattern), and
write `setup.sh` / `deploy.sh` / `cleanup.sh` / `cold-start-test.sh`,
with `setup.sh` importing this saved object automatically.
