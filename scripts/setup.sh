#!/bin/bash
set -e

cd "$(dirname "$0")/.."

echo "========================================"
echo " TTCPoint Setup (Docker Compose)"
echo "========================================"

echo ""
echo "[1/5] Starting Kafka and Elasticsearch..."
docker compose up -d kafka elasticsearch

echo ""
echo "[2/5] Waiting for Elasticsearch..."
until curl -sf http://localhost:9200/_cluster/health >/dev/null 2>&1; do
  sleep 3
done

echo ""
echo "[3/5] Applying Elasticsearch index template..."
# Must happen before Logstash writes anything - Elasticsearch infers a
# mapping from the first document it sees, and without this template
# "location" would be guessed as a plain object instead of geo_point,
# which isn't fixable later without reindexing.
curl -s -X PUT "http://localhost:9200/_index_template/vehicle-positions-template" \
  -H 'Content-Type: application/json' \
  -d @elasticsearch/templates/vehicle-positions-template.json
echo ""

echo ""
echo "[4/5] Starting Logstash, Kibana, and the producer..."
docker compose up -d --build logstash kibana producer

echo ""
echo "[5/5] Waiting for Kibana, then importing the saved map..."
until curl -sf http://localhost:5601/api/status >/dev/null 2>&1; do
  sleep 3
done
curl -s -X POST "http://localhost:5601/api/saved_objects/_import?overwrite=true" \
  -H "kbn-xsrf: true" \
  --form file=@kibana/saved-objects/ttc-map-and-dashboards.ndjson >/dev/null

echo ""
echo "========================================"
echo " TTCPoint is ready!"
echo "========================================"
echo "Kibana:        http://localhost:5601"
echo "Elasticsearch: http://localhost:9200"
