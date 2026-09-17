# TTC Live Transit Visualizer

A live map of Toronto's buses and streetcars, built on a real
Kafka → Logstash → Elasticsearch → Kibana streaming pipeline, fed by
TTC's free, public, no-API-key GTFS-realtime feed.

This is a standalone portfolio project focused on a distributed
streaming/search stack applied to real data — see also
[QuantPulse](https://github.com/Shreyas1705-OTU/QuantPulse), which
demonstrates a different kind of engineering rigor (test depth,
adversarial review, resilience testing) on a different stack. The two
are deliberately kept separate.

## What it does

TTC publishes live vehicle positions as a GTFS-realtime protobuf feed.
This project polls it, decodes it, and runs it through a real streaming
pipeline:

```
TTC GTFS-RT feed (protobuf, polled every 20s)
  -> Python producer decodes it into structured records
  -> Kafka (single broker, KRaft mode)
  -> Logstash (enriches route_id against static GTFS data,
               builds a geo_point, parses timestamps)
  -> Elasticsearch (geo-indexed documents)
  -> Kibana Maps  +  a standalone Leaflet frontend
     (two independent live views of the same data)
```

Scope is bus + streetcar only — TTC does not publish live GPS positions
for the subway (it's signal-based, not GPS-tracked), so there was no
live data to show for it.

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for prerequisites, a full
walkthrough of both paths, and troubleshooting for everything that
actually went wrong while building this.

## Quick start (Kubernetes - default)

This is the primary, "real" deployment path: a local Kind cluster
running every component as its own Deployment/Service, mirroring how
you'd actually run this on a real cluster.

```
./scripts/setup-kind.sh          # creates the Kind cluster
./scripts/deploy-kind.sh         # builds images, deploys everything
./scripts/port-forward-kind.sh   # exposes the services below
```

- Frontend (Leaflet): http://localhost:8080
- Kibana: http://localhost:5601
- Elasticsearch: http://localhost:9200

Tear down with `./scripts/cleanup-kind.sh`.

**Note for resource-constrained hosts** (e.g. WSL2 with limited RAM):
running the whole `deploy-kind.sh` script as one long background process
can trip a low-memory kill partway through image loading, even when the
host has memory available moments later - it's a transient spike, not a
real failure. If that happens, just re-run `deploy-kind.sh` (every step
is idempotent) or run its steps individually. `deploy-kind.sh` also
builds images with `--provenance=false --sbom=false`, since Docker's
default multi-manifest attestation output measurably increases what
`kind load docker-image` has to process for no benefit in a local demo.

## Quick start (Docker Compose - fast local dev)

Same pipeline, single command, no Kubernetes - useful for fast
iteration on the pipeline itself.

```
./scripts/setup.sh
```

- Frontend: http://localhost:8080
- Kibana: http://localhost:5601
- Elasticsearch: http://localhost:9200

Tear down with `./scripts/cleanup.sh`. `./scripts/cold-start-test.sh`
runs cleanup -> setup -> verifies real documents land in Elasticsearch,
from a completely clean state.

## Why two deployment paths

Compose is for iterating on the pipeline quickly. Kubernetes is the
default because it's the more honest demonstration of the "distributed
system" story this project is about - namespaces, generated ConfigMaps,
per-component Deployments/Services, rollout status, the same shape
you'd use on a real cluster, not a shortcut that only works because of
Compose's networking magic. Both were built, verified end-to-end with
real live data, and are kept in sync going forward.

## The two live views

**Kibana Maps** is the "operational" view - built with Kibana's own
tooling, saved as `kibana/saved-objects/ttc-map-and-dashboards.ndjson`,
auto-imported by both deploy scripts.

**The Leaflet frontend** (`frontend/`) is a small standalone page that
queries Elasticsearch directly from the browser (CORS enabled on
Elasticsearch for exactly this - no backend/proxy needed) and renders
its own dark-themed map. Same live data, same red-bus/purple-streetcar
color scheme, deliberately not styled like an admin tool.

## Repo layout

```
ingestion/     Python producer: decodes the GTFS-RT feed, publishes to Kafka
logstash/      Pipeline config: enrichment, geo_point shaping, ES output
elasticsearch/ Index template (geo_point mapping for location)
kibana/        Exported saved objects (the Maps visualization)
frontend/      Standalone Leaflet page (nginx-served)
k8s/           Kubernetes manifests, one directory per component
scripts/       setup/deploy/cleanup for both Compose and Kind
reviews/       Phase-by-phase build notes: what was decided and why,
               what broke, how it was verified - written as the
               project was actually built, not after the fact
```

## Data sources

- Live vehicle positions: `https://bustime.ttc.ca/gtfsrt/vehicles`
  (GTFS-realtime, protobuf, TTC's public surface-routes feed)
- Static route/stop data: Toronto Open Data's TTC Routes and Schedules
  dataset, resolved dynamically via the CKAN API since resource URLs
  rotate roughly every 6 weeks when TTC republishes it

No API key required for either.
