#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Cleaning up CarModPicker Kubernetes deployment..."

# Change to the script directory
cd "$SCRIPT_DIR"

# Delete ingress
echo "Deleting ingress..."
kubectl delete -f ingress.yaml --ignore-not-found=true

# Delete frontend services (from frontend directory)
echo "Deleting frontend services..."
kubectl delete -f ../../CarModPicker-Frontend/kubernetes/frontend-service.yaml --ignore-not-found=true
kubectl delete -f ../../CarModPicker-Frontend/kubernetes/frontend-deployment.yaml --ignore-not-found=true

# Delete backend services
echo "Deleting backend services..."
kubectl delete -f . --ignore-not-found=true

# Delete nginx ingress controller
echo "Deleting nginx ingress controller..."
kubectl delete -f nginx-ingress-controller.yaml --ignore-not-found=true

# Delete nginx ingress RBAC
echo "Deleting nginx ingress RBAC..."
kubectl delete -f nginx-ingress-rbac.yaml --ignore-not-found=true

# Delete ingress-nginx namespace
echo "Deleting ingress-nginx namespace..."
kubectl delete namespace ingress-nginx --ignore-not-found=true

echo "Cleanup complete!" 