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

echo "Cleaning up Example Voting App..."

for manifest in \
    worker-deployment.yaml \
    result-deployment.yaml result-service.yaml \
    vote-deployment.yaml vote-service.yaml \
    redis-deployment.yaml redis-service.yaml \
    db-deployment.yaml db-service.yaml; do
    echo "Removing $manifest..."
    kubectl delete -f "$K8S_DIR/$manifest" --ignore-not-found=true
done

for pattern in '*pvc*.yaml' '*pv*.yaml'; do
    for manifest in "$K8S_DIR"/$pattern; do
        [[ -f "$manifest" ]] || continue
        echo "Removing storage manifest: $(basename "$manifest")"
        kubectl delete -f "$manifest" --ignore-not-found=true
    done
done

echo
echo "Cleanup complete. Remaining app resources:"
kubectl get pods,services
