#!/bin/bash
set -e

cd "$(dirname "$0")/.."

echo "========================================"
echo " TTCPoint Kubernetes Deployment"
echo "========================================"

echo ""
echo "[1/10] Building producer and frontend images..."
docker build -t ttcpoint-producer:latest ./ingestion
docker build -t ttcpoint-frontend:latest ./frontend

echo ""
echo "[2/10] Loading images into Kind..."
kind load docker-image ttcpoint-producer:latest --name ttcpoint
kind load docker-image ttcpoint-frontend:latest --name ttcpoint

echo ""
echo "[3/10] Creating namespace..."
kubectl apply -f k8s/namespace.yaml

echo ""
echo "[4/10] Generating ConfigMaps from repo source files..."
# Generated, not hand-duplicated, so logstash/ and data/lookups/ stay the
# single source of truth instead of drifting from a second copy in k8s/.
kubectl create configmap logstash-pipeline \
  --from-file=logstash/pipeline/ \
  -n ttcpoint --dry-run=client -o yaml | kubectl apply -f -

kubectl create configmap logstash-config \
  --from-file=logstash/config/logstash.yml \
  -n ttcpoint --dry-run=client -o yaml | kubectl apply -f -

kubectl create configmap route-lookups \
  --from-file=data/lookups/route_short_name.yml \
  --from-file=data/lookups/route_color.yml \
  --from-file=data/lookups/route_type.yml \
  -n ttcpoint --dry-run=client -o yaml | kubectl apply -f -

echo ""
echo "[5/10] Deploying Kafka..."
kubectl apply -f k8s/kafka/
kubectl rollout status deployment/kafka -n ttcpoint --timeout=180s

echo ""
echo "Creating vehicle-positions topic..."
kubectl exec deployment/kafka -n ttcpoint -- \
  /opt/kafka/bin/kafka-topics.sh --create --if-not-exists \
  --topic vehicle-positions --bootstrap-server localhost:29092 \
  --partitions 3 --replication-factor 1

echo ""
echo "[6/10] Deploying Elasticsearch..."
kubectl apply -f k8s/elasticsearch/
kubectl rollout status deployment/elasticsearch -n ttcpoint --timeout=180s

echo ""
echo "[7/10] Applying Elasticsearch index template..."
# Must happen before Logstash writes anything, same reasoning as
# scripts/setup.sh (the compose path) - see that script's comment.
kubectl port-forward svc/elasticsearch 9200:9200 -n ttcpoint >/dev/null 2>&1 &
ES_PF_PID=$!
trap 'kill $ES_PF_PID 2>/dev/null || true' EXIT

until curl -sf http://localhost:9200/_cluster/health >/dev/null 2>&1; do
  sleep 2
done
curl -s -X PUT "http://localhost:9200/_index_template/vehicle-positions-template" \
  -H 'Content-Type: application/json' \
  -d @elasticsearch/templates/vehicle-positions-template.json
echo ""

kill $ES_PF_PID 2>/dev/null || true
trap - EXIT

echo ""
echo "[8/10] Deploying Logstash, Kibana, the producer, and the frontend..."
kubectl apply -f k8s/logstash/
kubectl apply -f k8s/kibana/
kubectl apply -f k8s/producer/
kubectl apply -f k8s/frontend/

# :latest tags and ConfigMap-only changes both look "unchanged" to
# kubectl apply, so a redeploy with new code/config wouldn't otherwise
# restart the already-running pod. Force it every run - same reasoning
# as QuantPulse's deploy-kind.sh.
kubectl rollout restart deployment/logstash -n ttcpoint
kubectl rollout restart deployment/producer -n ttcpoint

echo ""
echo "[9/10] Waiting for deployments, then importing the saved map..."
kubectl rollout status deployment/logstash -n ttcpoint --timeout=180s
kubectl rollout status deployment/kibana -n ttcpoint --timeout=180s
kubectl rollout status deployment/producer -n ttcpoint --timeout=180s
kubectl rollout status deployment/frontend -n ttcpoint --timeout=180s

kubectl port-forward svc/kibana 5601:5601 -n ttcpoint >/dev/null 2>&1 &
KIBANA_PF_PID=$!
trap 'kill $KIBANA_PF_PID 2>/dev/null || true' EXIT

until curl -sf http://localhost:5601/api/status >/dev/null 2>&1; do
  sleep 2
done
curl -s -X POST "http://localhost:5601/api/saved_objects/_import?overwrite=true" \
  -H "kbn-xsrf: true" \
  --form file=@kibana/saved-objects/ttc-map-and-dashboards.ndjson >/dev/null

kill $KIBANA_PF_PID 2>/dev/null || true
trap - EXIT

echo ""
echo "========================================"
echo " TTCPoint deployed successfully!"
echo "========================================"

echo ""
echo "Start port forwarding:"
echo "./scripts/port-forward-kind.sh"

echo ""
kubectl get pods -n ttcpoint
