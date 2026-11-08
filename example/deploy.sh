#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$SCRIPT_DIR/db-deployment.yaml" ]]; then
    K8S_DIR="$SCRIPT_DIR"
else
    K8S_DIR="$SCRIPT_DIR/k8s-specifications"
fi

if ! command -v kubectl >/dev/null 2>&1; then
    echo "Error: kubectl is not installed or not available in PATH." >&2
    exit 1
fi

if [[ ! -f "$K8S_DIR/db-deployment.yaml" ]]; then
    echo "Error: Could not find db-deployment.yaml beside the script or in its k8s-specifications subdirectory." >&2
    exit 1
fi

echo "Deploying Example Voting App..."

for pattern in '*pv*.yaml' '*pvc*.yaml'; do
    for manifest in "$K8S_DIR"/$pattern; do
        [[ -f "$manifest" ]] || continue
        echo "Applying storage manifest: $(basename "$manifest")"
        kubectl apply -f "$manifest"
    done
done

echo "Deploying database..."
kubectl apply -f "$K8S_DIR/db-service.yaml"
kubectl apply -f "$K8S_DIR/db-deployment.yaml"

echo "Deploying Redis..."
kubectl apply -f "$K8S_DIR/redis-service.yaml"
kubectl apply -f "$K8S_DIR/redis-deployment.yaml"

echo "Deploying voting app..."
kubectl apply -f "$K8S_DIR/vote-service.yaml"
kubectl apply -f "$K8S_DIR/vote-deployment.yaml"

echo "Deploying results app..."
kubectl apply -f "$K8S_DIR/result-service.yaml"
kubectl apply -f "$K8S_DIR/result-deployment.yaml"

echo "Deploying worker..."
kubectl apply -f "$K8S_DIR/worker-deployment.yaml"

echo
echo "Deployment resources:"
kubectl get pods,services

echo
echo "Voting app:  http://<node-ip>:31000"
echo "Results app: http://<node-ip>:31001"
echo "Use 'kubectl get nodes -o wide' to find a node IP."
