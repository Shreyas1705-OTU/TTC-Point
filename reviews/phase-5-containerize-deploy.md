# Phase 5 Review — Containerize + Deploy Scripts

## Goal
Make the whole Phase 1-4 pipeline reproducible by one command, not by
remembering manual steps - matching QuantPulse's deployment discipline
(containerized, scripted setup/deploy/cleanup, cold-start tested) even
though this project doesn't chase QuantPulse's testing depth.

## Decisions made
- **Two deployment paths, both scripted**: `docker-compose.yml` for local
  dev (fast iteration), and Kubernetes manifests on a Kind cluster for
  the "real deployment" story - reusing QuantPulse's actual pattern
  (`kind-config.yaml`, per-component `k8s/<name>/deployment.yaml` +
  `service.yaml`, `scripts/setup-kind.sh` creates the cluster,
  `scripts/deploy-kind.sh` builds/loads images and applies manifests,
  `scripts/cleanup-kind.sh` tears it down, `scripts/port-forward-kind.sh`
  exposes services) - copied from `~/Projects/QuantPulse` directly rather
  than reinvented.
- **Kafka bootstrap address made configurable** (`KAFKA_BOOTSTRAP_SERVERS`
  env var, defaulting to `localhost:9092` for host runs from Phases 1-4)
  so the same producer image/code works in Compose, in Kind, and still
  works if run directly on the host.
- **k8s ConfigMaps generated from repo files, not hand-duplicated.**
  `logstash/pipeline/`, `logstash/config/logstash.yml`, and
  `data/lookups/*.yml` are the single source of truth; `deploy-kind.sh`
  runs `kubectl create configmap ... --dry-run=client -o yaml | kubectl
  apply -f -` against them rather than maintaining a second copy of the
  same content as static YAML in `k8s/`.
- **No PVCs.** Kafka and Elasticsearch both run as plain Deployments with
  ephemeral storage (`emptyDir` for Elasticsearch's data dir) - this is
  live vehicle state, not a system of record, so losing data on a pod
  restart is an acceptable, deliberate tradeoff (matches the original
  "short retention, live state not deep history" framing from the plan).
- **Elasticsearch index template applied via a temporary port-forward**
  inside `deploy-kind.sh` (same as `setup.sh`'s direct `curl` in Compose) -
  must land before Logstash indexes anything, for the same reason as
  Phase 3 (Elasticsearch infers a wrong mapping from the first document
  otherwise, and that's not fixable without reindexing).
- **Kibana saved object import automated in both paths.** Initially
  missed this in `deploy-kind.sh` (only `setup.sh` had it) - caught
  during review and added, so a fresh Kind deploy also ends with the
  live map already there, not requiring manual re-creation.

## Real bug found and fixed: port mismatch between environments
`logstash/pipeline/vehicle-positions.conf` is shared unchanged between
Compose (bind-mounted) and k8s (mounted from a generated ConfigMap), and
hardcodes `bootstrap_servers => "kafka:29092"` - the INTERNAL listener
port from the Phase 2 dual-listener Kafka setup in Compose. The first k8s
Kafka manifest only exposed port `9092` (a single listener was correct -
no host-vs-container split needed in k8s, since nothing runs outside a
pod), so Logstash spent several minutes failing to connect
(`Bootstrap broker kafka:29092 disconnected`, repeating) before this was
caught by actually reading Logstash's logs instead of assuming a clean
`kubectl apply` meant it worked.

Fix: kept Kafka's single k8s listener on port **29092** (not 9092) so the
one pipeline config file works unchanged in both environments, rather
than adding environment-specific templating. Updated
`k8s/kafka/deployment.yaml`, `k8s/kafka/service.yaml`,
`k8s/producer/deployment.yaml`, and the topic-creation command in
`deploy-kind.sh` to match.

## Other things hit
- A background `deploy-kind.sh` run was killed by the harness for low
  host memory partway through (Kafka + Elasticsearch + Logstash's 1GB JVM
  heap + Kibana all starting at once on a resource-constrained WSL2
  host). Not a bug in the deployment itself - re-running the (idempotent)
  script after freeing memory completed cleanly; pulling the ~550MB
  Elastic images from a cold Kind node cache also just takes real time
  (over a minute each), which the original `kubectl rollout status`
  timeouts didn't generously account for on a loaded host.
- Producer container logs appeared empty at first - Python buffers
  stdout when it isn't attached to a TTY, so nothing showed up until the
  buffer filled or the process exited. Fixed with `ENV
  PYTHONUNBUFFERED=1` in `ingestion/Dockerfile`.

## What was built
- `ingestion/Dockerfile` - the producer, containerized.
- `docker-compose.yml` extended with a `producer` service alongside the
  Phase 2-4 services.
- `scripts/setup.sh`, `scripts/cleanup.sh`, `scripts/cold-start-test.sh`
  (Compose path).
- `kind-config.yaml`, `k8s/namespace.yaml`,
  `k8s/{kafka,elasticsearch,logstash,kibana,producer}/`,
  `scripts/setup-kind.sh`, `scripts/deploy-kind.sh`,
  `scripts/cleanup-kind.sh`, `scripts/port-forward-kind.sh` (Kind path).

## Verification (actual results)
- **Compose cold-start test, run for real**: `scripts/cold-start-test.sh`
  (`cleanup.sh` -> `setup.sh` -> poll until documents appear) succeeded
  from a totally clean state - **1886 documents indexed**, Kibana map
  confirmed importable via the saved-objects API.
- **Kind deployment, run for real**: `setup-kind.sh` then `deploy-kind.sh`
  against an actual Kind cluster on this machine. After the port-mismatch
  fix above, all 5 pods reached `1/1 Running`
  (`kafka`, `elasticsearch`, `logstash`, `kibana`, `producer`), and a
  direct Elasticsearch query (via `kubectl port-forward`) confirmed
  **17,594 real, correctly-enriched documents** (`route_short_name`,
  `route_color`, `route_type` all populated correctly). The Kibana map
  saved object imports cleanly against the k8s deployment too.

## Outcome
Both deployment paths are real, scripted, and were actually exercised
end-to-end on this machine (not just written and assumed correct) - one
config-sharing bug was caught specifically because of that. Cold-start
tested for Compose; Kind path deployed, fixed, and verified with live
data, matching the discipline the plan called for.

## Next phase
Phase 6 — polish: route filtering/coloring refinement, README (with the
"see also: QuantPulse" link), and a discussion of the explicitly-optional
stretch goals (service alerts, a custom Leaflet frontend) before building
either.
