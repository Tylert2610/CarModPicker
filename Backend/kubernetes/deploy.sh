#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Deploying CarModPicker to Kubernetes..."

# Change to the script directory
cd "$SCRIPT_DIR"

# Create namespace for ingress-nginx if it doesn't exist
kubectl create namespace ingress-nginx --dry-run=client -o yaml | kubectl apply -f -

# Apply RBAC for nginx ingress controller
echo "Applying nginx ingress RBAC..."
kubectl apply -f nginx-ingress-rbac.yaml

# Apply nginx ingress controller
echo "Applying nginx ingress controller..."
kubectl apply -f nginx-ingress-controller.yaml

# Wait for nginx ingress controller to be ready
echo "Waiting for nginx ingress controller to be ready..."
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/name=ingress-nginx \
  --timeout=120s

# Apply backend services
echo "Applying backend services..."
kubectl apply -f .

# Apply frontend services (from frontend directory)
echo "Applying frontend services..."
kubectl apply -f ../../CarModPicker-Frontend/kubernetes/frontend-service.yaml
kubectl apply -f ../../CarModPicker-Frontend/kubernetes/frontend-deployment.yaml

# Apply ingress
echo "Applying ingress..."
kubectl apply -f ingress.yaml

echo "Deployment complete!"
echo ""
echo "To access your application:"
echo "Frontend: http://localhost"
echo "Backend API: http://localhost/api"
echo ""
echo "If you can't access the application, check:"
echo "1. kubectl get pods -A"
echo "2. kubectl get services -A"
echo "3. kubectl get ingress -A"
echo "4. kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx" 