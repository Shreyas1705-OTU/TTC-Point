#!/bin/bash
set -e

cd "$(dirname "$0")/.."

./scripts/cleanup.sh
./scripts/setup.sh

echo ""
echo "Waiting for real vehicle documents to appear in Elasticsearch..."
for i in $(seq 1 30); do
  count=$(curl -s http://localhost:9200/vehicle-positions/_count 2>/dev/null \
    | python3 -c "import json,sys; print(json.load(sys.stdin).get('count', 0))" 2>/dev/null || echo 0)
  if [ "$count" -gt 0 ]; then
    echo ""
    echo "SUCCESS: $count documents indexed from a cold start."
    exit 0
  fi
  sleep 5
done

echo ""
echo "FAILURE: no documents appeared within the timeout." >&2
exit 1
