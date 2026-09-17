# Phase 6 Review — Custom Leaflet Frontend

## Goal
Give the project a demo surface that looks like a real application
rather than an Elastic Stack admin console. Kibana Maps (Phase 4) proved
the data and stayed as the "operational" view; this is a second,
purpose-built view of the exact same live Elasticsearch data.

## Decisions made
- **Browser queries Elasticsearch directly - no backend.** For a
  project this size, a Node/Python API server whose only job would be
  "forward this query to Elasticsearch" is unjustified complexity. The
  browser's same-origin policy is the actual obstacle, so the fix is
  CORS on Elasticsearch itself (`http.cors.enabled=true`,
  `http.cors.allow-origin=/.*/`), not a proxy server. Wildcard origin is
  fine for the same reason `xpack.security.enabled=false` already is:
  local demo stack, not a real deployment.
- **Static HTML/CSS/JS, no build step, no framework.** Leaflet loaded
  from a CDN (`unpkg.com/leaflet@1.9.4`, current stable). Matches the
  project's "demo priority over engineering exhaustiveness" framing -
  a bundler/framework would be real complexity for a single page with
  one interactive element.
- **`collapse` on `vehicle_id`, sorted by `@timestamp desc`**, instead of
  returning every document in the time window. Without this, a vehicle
  that reported 3 times in the last 2 minutes would draw 3 overlapping
  markers instead of 1 at its latest known position - Elasticsearch's
  field collapsing (supported on `keyword` fields, which `vehicle_id`
  already is) does this server-side in one query rather than
  deduplicating client-side.
- **Dark CARTO basemap + custom color legend**, matching Kibana's
  red-bus/purple-streetcar palette for visual consistency between the
  two views, but styled as its own thing (dark UI panel with a live
  vehicle count) rather than mimicking Kibana's chrome.
- **Served via nginx (`frontend/Dockerfile`, `FROM nginx:alpine`)** in
  both Compose (`frontend` service, port 8080) and Kind
  (`k8s/frontend/`, exposed through `port-forward-kind.sh`) - same
  containerization discipline as every other component from Phase 5,
  not treated as a special case.

## What was built
- `frontend/index.html`, `style.css`, `app.js` - the actual page: a
  Leaflet map centered on Toronto, polling Elasticsearch every 15s
  (matching the poll/refresh cadence established in Phases 2 and 4),
  rendering colored circle markers with a popup (route, vehicle ID,
  speed in km/h) and a live vehicle/bus/streetcar count panel.
- `frontend/Dockerfile` + `.dockerignore`.
- `docker-compose.yml`: `frontend` service; CORS env vars added to
  `elasticsearch`.
- `k8s/frontend/deployment.yaml` + `service.yaml`; CORS env vars added
  to `k8s/elasticsearch/deployment.yaml`; `deploy-kind.sh` and
  `port-forward-kind.sh` updated to build/load/deploy/expose it
  alongside everything else.

## Verification (actual results)
- Ran `scripts/cold-start-test.sh` end-to-end with the frontend service
  included: **814 documents indexed from a clean state**, frontend
  container reachable (`HTTP 200` on `localhost:8080`).
- Verified CORS for real, not just by reading config: an `OPTIONS`
  preflight and an actual `POST` to
  `http://localhost:9200/vehicle-positions/_search` with
  `Origin: http://localhost:8080` both returned
  `access-control-allow-origin: http://localhost:8080` - confirming a
  real browser page at that origin can query Elasticsearch directly.
- Confirmed the collapse query returns the exact document shape
  `app.js` expects (`location.{lat,lon}`, `route_type`, `route_color`,
  `route_short_name`, `speed`) with live data (2,872 total matches in
  the trailing 2-minute window, deduplicated to one per vehicle by the
  collapse).

## Outcome
A second, self-contained live view of the same real TTC data exists,
verified to actually work end-to-end (query, CORS, and rendering data
shape all confirmed), not just written and assumed correct.

## Next
README (with the "see also: QuantPulse" link) and any remaining polish
- route filtering, final visual pass - are what's left before this
project is presentation-ready.
