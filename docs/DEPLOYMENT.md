# Deployment Handbook

Detailed walkthrough for running TTCPoint yourself, plus a
troubleshooting section covering everything that actually broke while
building it — not hypothetical issues, real ones hit and fixed during
development (see `reviews/` for the full blow-by-blow).

## Prerequisites

| Tool | Used for | Verified with |
|---|---|---|
| Docker + Docker Compose | Both deployment paths | Docker 29.x, Compose v2.40.x |
| [kind](https://kind.sigs.k8s.io/) | Kubernetes path | 0.33.x |
| kubectl | Kubernetes path | 1.36.x |
| `curl`, `python3` | The scripts themselves (health checks, JSON parsing) | any recent version |

No API keys, no accounts, no paid services anywhere in this stack.
That's a deliberate project constraint, not an oversight — see
`reviews/phase-6-leaflet-frontend.md` for a case where a dependency
(CARTO's map tiles) quietly started requiring one and had to be swapped
out.

## Path 1: Kubernetes (Kind) — the default

```
./scripts/setup-kind.sh
./scripts/deploy-kind.sh
./scripts/port-forward-kind.sh
```

**`setup-kind.sh`** creates a single-node Kind cluster named `ttcpoint`.
Nothing else — no ingress controller, since nothing here needs
host-level routing rules (unlike a project with a public-facing
frontend service).

**`deploy-kind.sh`** does everything else, in order:
1. Builds the `producer` and `frontend` images locally (with
   `--provenance=false --sbom=false` — see Troubleshooting below for
   why that flag matters).
2. Loads both images into the Kind node (`kind load docker-image`) —
   images built locally aren't visible inside the cluster otherwise.
3. Creates the `ttcpoint` namespace.
4. Generates three ConfigMaps directly from repo files (`kubectl create
   configmap ... --from-file=... --dry-run=client -o yaml | kubectl
   apply -f -`) rather than maintaining hand-written duplicates:
   `logstash-pipeline`, `logstash-config`, `route-lookups`.
5. Deploys Kafka, waits for it to be ready, creates the
   `vehicle-positions` topic (3 partitions, replication factor 1).
6. Deploys Elasticsearch, waits for it to be ready, then applies the
   index template (`elasticsearch/templates/vehicle-positions-template.json`)
   via a temporary `kubectl port-forward` — this has to happen *before*
   any document is indexed, or Elasticsearch guesses the wrong mapping
   for `location` (a plain object instead of `geo_point`) from the
   first document, which isn't fixable without reindexing.
7. Deploys Logstash, Kibana, the producer, and the frontend; force-
   restarts Logstash and the producer (`:latest` tags and ConfigMap-only
   changes both look "unchanged" to `kubectl apply`, so a redeploy with
   new code/config wouldn't otherwise touch the already-running pod).
8. Waits for every deployment to report ready, then imports the saved
   Kibana map (`kibana/saved-objects/ttc-map-and-dashboards.ndjson`) the
   same way as step 6 — a temporary port-forward, one `curl`.

**`port-forward-kind.sh`** exposes Kibana (`:5601`), Elasticsearch
(`:9200`), and the frontend (`:8080`) on your machine. Runs in the
foreground; `Ctrl+C` stops all three forwards together.

Tear down with `./scripts/cleanup-kind.sh` (deletes the whole Kind
cluster).

### Verifying it actually worked

Don't just trust that the scripts exited 0 — check real data exists:

```
curl http://localhost:9200/vehicle-positions/_count
```

Should return a growing count within ~30-60s of the producer starting
(TTC's own feed lags real time by 20-50s — see Troubleshooting). Then
open `http://localhost:8080` or `http://localhost:5601` and look for
moving dots over Toronto.

## Path 2: Docker Compose — fast local iteration

```
./scripts/setup.sh
```

Same sequence as `deploy-kind.sh` conceptually (start Kafka +
Elasticsearch, apply the index template, then start everything else and
import the saved map), just via `docker compose up` instead of
`kubectl apply`. Tear down with `./scripts/cleanup.sh`.

`./scripts/cold-start-test.sh` runs `cleanup.sh` → `setup.sh` → polls
Elasticsearch until real documents appear (30 × 5s), exiting non-zero if
none show up within the timeout. Use this whenever you want a real
"did I break anything" check, not just "did the containers start."

## Troubleshooting

**Low-memory kill partway through `deploy-kind.sh`, specifically during
image loading.** Hit repeatedly on a resource-constrained WSL2 host
(7.7GB RAM) while building this. Two contributing factors, both already
fixed in the scripts, but worth knowing if it still happens on your
machine:
- Docker's default build output now includes provenance/SBOM
  attestations, producing a multi-manifest image instead of a plain
  one — `kind load docker-image` has measurably more to process as a
  result. `deploy-kind.sh` already builds with `--provenance=false
  --sbom=false` to avoid this.
- Running the *entire* multi-minute script as one long backgrounded
  process seemed to compound memory pressure in a way that running the
  same steps individually, in the foreground, did not — even though
  each individual step (e.g. `kind load docker-image`) completed in
  2-3 seconds when run alone. If a full run still gets killed, every
  step in `deploy-kind.sh` is idempotent — just re-run it, or run the
  commands inside it one at a time.

**Logstash can't connect to Kafka (`Bootstrap broker kafka:29092
disconnected`, repeating).** This bit us once during development: the
Logstash pipeline config is shared byte-for-byte between Compose and
Kubernetes, and hardcodes `kafka:29092`. If you ever change
`k8s/kafka/deployment.yaml` or `service.yaml`'s listener port, you must
change it in both places, or Logstash will fail to connect while
`kubectl get pods` still shows everything `Running` (the pod is up; it's
just failing to talk to Kafka) — check `kubectl logs deployment/logstash
-n ttcpoint` if documents stop appearing.

**A time window narrower than ~1 minute shows no data on either map.**
Not a bug — TTC's own feed lags real time by 20-50 seconds before it
ever reaches this pipeline (confirmed by comparing the feed's own
timestamps against wall-clock time; see
`reviews/phase-4-kibana-maps.md`). Both the Kibana map and the Leaflet
frontend default to a 2-minute window for exactly this reason. Don't
narrow it below ~1 minute expecting more "live" results — you'll just
get empty gaps.

**Map tiles show "API KEY REQUIRED".** If you ever swap the Leaflet
frontend's tile provider, double-check it's actually free/key-free
before committing to it — CARTO's basemap CDN started requiring one at
some point after this project initially used it, and every tile
silently rendered a watermark instead of failing loudly. Currently uses
plain OpenStreetMap tiles (`tile.openstreetmap.org`, no key, ever) with
a CSS filter for the dark look.

**`logstash.yml` config errors on startup
(`Setting "http.host" doesn't exist`).** Elastic Stack config keys do
change between versions. This project pins Elasticsearch/Logstash/Kibana
to `9.5.4` for exactly this reason — if you bump the version, check the
Elastic Stack changelog for renamed/removed settings before assuming
`logstash/config/logstash.yml` still works unchanged.

**Producer container logs look empty.** Python buffers stdout when it
isn't attached to a terminal, so nothing shows up in `docker logs` /
`kubectl logs` until the buffer fills or the process exits.
`ingestion/Dockerfile` sets `PYTHONUNBUFFERED=1` for exactly this reason
— if you're still seeing nothing, check the pod/container actually
started (`kubectl get pods` / `docker ps`) before assuming it's silently
failing.

## Further reading

`reviews/phase-*.md` — one file per build phase, written as the project
was actually built: what was decided and why, what broke, and how each
phase was verified with real data before moving on. More narrative detail
than this handbook; read them if you want the reasoning, not just the
fix.
