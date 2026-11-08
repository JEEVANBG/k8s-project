#!/bin/bash

echo "🧹 Cleaning up K8s demo application..."

echo "  → Removing ingress..."
kubectl delete -f k8s/ingress.yaml --ignore-not-found=true

echo "  → Removing frontend..."
kubectl delete -f k8s/frontend-service.yaml --ignore-not-found=true
kubectl delete -f k8s/frontend-deployment.yaml --ignore-not-found=true

echo "  → Removing backend..."
kubectl delete -f k8s/backend-service.yaml --ignore-not-found=true
kubectl delete -f k8s/backend-deployment.yaml --ignore-not-found=true

echo "  → Removing database..."
kubectl delete -f k8s/postgres-service.yaml --ignore-not-found=true
kubectl delete -f k8s/postgres-deployment.yaml --ignore-not-found=true

echo "  → Removing configs..."
kubectl delete -f k8s/backend-configmap.yaml --ignore-not-found=true

echo "  → Removing storage..."
kubectl delete -f k8s/postgres-pv.yaml --ignore-not-found=true

echo "  → Removing secrets..."
kubectl delete -f k8s/postgres-secret.yaml --ignore-not-found=true

echo "✅ Cleanup complete!"

echo ""
echo "📊 Remaining resources:"
kubectl get all --selector="app in (frontend,backend,postgres)" || echo "No resources found"