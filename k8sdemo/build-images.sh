#!/bin/bash

set -e

echo "🚀 Building Docker images for K8s demo app..."

echo "📦 Building backend image..."
cd backend
docker build -t k8s-demo-backend:latest .
cd ..

echo "📦 Building frontend image..."
cd frontend
docker build -t k8s-demo-frontend:latest .
cd ..

echo "✅ All images built successfully!"

echo "📋 Available images:"
docker images | grep k8s-demo

echo ""
echo "💡 Next steps:"
echo "1. Start your Kubernetes cluster (minikube start)"
echo "2. Load images to cluster: ./load-images.sh"
echo "3. Deploy the application: ./deploy.sh"