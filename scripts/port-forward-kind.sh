#!/bin/bash

echo "========================================"
echo " TTCPoint Port Forwarding (Kind)"
echo "========================================"

echo ""
echo "Starting Kibana on :5601..."
kubectl port-forward svc/kibana 5601:5601 -n ttcpoint &
KIBANA_PID=$!

echo "Starting Elasticsearch on :9200..."
kubectl port-forward svc/elasticsearch 9200:9200 -n ttcpoint &
ES_PID=$!

echo ""
echo "Kibana:"
echo "http://localhost:5601"
echo "Elasticsearch:"
echo "http://localhost:9200"

echo ""
echo "Press Ctrl+C to stop port forwarding."

trap "kill $KIBANA_PID $ES_PID" EXIT

wait
