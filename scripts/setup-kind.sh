#!/bin/bash
set -e

cd "$(dirname "$0")/.."

echo "========================================"
echo " TTCPoint Kind Cluster Setup"
echo "========================================"

echo ""
echo "Creating Kind cluster..."
kind create cluster --config kind-config.yaml --name ttcpoint

echo ""
echo "========================================"
echo " Kind cluster is ready!"
echo "========================================"

echo ""
kubectl cluster-info

echo ""
echo "Next step:"
echo "./scripts/deploy-kind.sh"
