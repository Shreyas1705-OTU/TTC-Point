#!/bin/bash
set -e

cd "$(dirname "$0")/.."

echo "========================================"
echo " Cleaning TTCPoint (Docker Compose)"
echo "========================================"

echo ""
echo "Stopping containers and removing volumes..."
docker compose down -v

# Phases 1-4 sometimes ran the producer directly on the host (venv) rather
# than as its own container - clean that up too so a re-run of setup.sh
# doesn't end up with two producers double-publishing to Kafka.
pkill -f "python.*ttc_producer.py" 2>/dev/null || true

echo ""
echo "TTCPoint cleaned up."
