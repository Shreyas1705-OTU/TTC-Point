#!/bin/bash
set -e

echo "========================================"
echo " Cleaning TTCPoint (Kind)"
echo "========================================"

echo ""
echo "Deleting Kind cluster..."
kind delete cluster --name ttcpoint

echo ""
echo "TTCPoint Kind cluster deleted successfully."
