#!/bin/bash

set -e

echo "📥 Loading Docker images to Kubernetes cluster..."

# Check if minikube is running
if command -v minikube &> /dev/null && minikube status &> /dev/null; then
    echo "🔄 Loading images to minikube..."
    minikube image load k8s-demo-backend:latest
    minikube image load k8s-demo-frontend:latest
    echo "✅ Images loaded to minikube successfully!"
elif command -v kind &> /dev/null; then
    echo "🔄 Loading images to kind cluster..."
    kind load docker-image k8s-demo-backend:latest
    kind load docker-image k8s-demo-frontend:latest
    echo "✅ Images loaded to kind cluster successfully!"
else
    echo "⚠️  No local cluster detected (minikube/kind)"
    echo "📝 Make sure your cluster can access these images:"
    echo "   - k8s-demo-backend:latest"
    echo "   - k8s-demo-frontend:latest"
fi

echo ""
echo "💡 Next step: Deploy the application with ./deploy.sh"