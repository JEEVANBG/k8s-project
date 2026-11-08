#!/bin/bash

set -e

echo "🚀 Deploying K8s demo application..."

echo "📝 Applying Kubernetes manifests..."

echo "  → Creating secrets..."
kubectl apply -f k8s/postgres-secret.yaml

echo "  → Setting up persistent storage..."
kubectl apply -f k8s/postgres-pv.yaml

echo "  → Creating config maps..."
kubectl apply -f k8s/backend-configmap.yaml

echo "  → Deploying database..."
kubectl apply -f k8s/postgres-deployment.yaml
kubectl apply -f k8s/postgres-service.yaml

echo "  → Deploying backend..."
kubectl apply -f k8s/backend-deployment.yaml
kubectl apply -f k8s/backend-service.yaml

echo "  → Deploying frontend..."
kubectl apply -f k8s/frontend-deployment.yaml
kubectl apply -f k8s/frontend-service.yaml

echo "  → Setting up ingress..."
kubectl apply -f k8s/ingress.yaml

echo "✅ Deployment complete!"

echo ""
echo "📊 Checking deployment status..."
kubectl get pods,svc,ingress

echo ""
echo "⏳ Waiting for pods to be ready..."
kubectl wait --for=condition=ready pod -l app=postgres --timeout=120s
kubectl wait --for=condition=ready pod -l app=backend --timeout=120s
kubectl wait --for=condition=ready pod -l app=frontend --timeout=120s

echo ""
echo "🎉 Application is ready!"
echo ""
echo "📍 Access your application:"
if command -v minikube &> /dev/null && minikube status &> /dev/null; then
    echo "   Add to /etc/hosts: $(minikube ip) k8s-demo.local"
    echo "   Then visit: http://k8s-demo.local"
    echo "   Or run: minikube service frontend-service --url"
else
    echo "   Add to /etc/hosts: <cluster-ip> k8s-demo.local"
    echo "   Then visit: http://k8s-demo.local"
fi

echo ""
echo "🔧 Useful commands:"
echo "   View pods: kubectl get pods"
echo "   View logs: kubectl logs -f deployment/backend-deployment"
echo "   Delete app: ./cleanup.sh"