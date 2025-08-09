# Kubernetes Ingress Troubleshooting Guide

## Common Issues and Solutions

### 1. Cannot access application from outside cluster

**Symptoms:**

- Pods are running but can't reach from browser
- Connection refused or timeout errors

**Solutions:**

1. Check if ingress controller is running:

   ```bash
   kubectl get pods -n ingress-nginx
   ```

2. Check ingress controller logs:

   ```bash
   kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx
   ```

3. Verify ingress is configured correctly:

   ```bash
   kubectl get ingress -A
   kubectl describe ingress carmodpicker-ingress
   ```

4. Check if services are properly configured:
   ```bash
   kubectl get services -A
   kubectl describe service carmodpicker-frontend-svc
   kubectl describe service carmodpicker-backend-svc
   ```

### 2. Docker Desktop specific issues

**Symptoms:**

- LoadBalancer services stuck in pending
- Can't access via localhost

**Solutions:**

1. Ensure you're using NodePort instead of LoadBalancer
2. Check if Docker Desktop Kubernetes is enabled
3. Verify port mappings in Docker Desktop settings

### 3. Backend API not accessible

**Symptoms:**

- Frontend loads but API calls fail
- 404 errors on /api endpoints

**Solutions:**

1. Check backend service configuration:

   ```bash
   kubectl describe service carmodpicker-backend-svc
   ```

2. Verify backend pods are running:

   ```bash
   kubectl get pods -l app=carmodpicker-backend
   ```

3. Check backend logs:
   ```bash
   kubectl logs -l app=carmodpicker-backend
   ```

### 4. Frontend not loading

**Symptoms:**

- Browser shows connection refused
- Nginx errors

**Solutions:**

1. Check frontend service:

   ```bash
   kubectl describe service carmodpicker-frontend-svc
   ```

2. Verify frontend pods:

   ```bash
   kubectl get pods -l app=carmodpicker-frontend
   ```

3. Check frontend logs:
   ```bash
   kubectl logs -l app=carmodpicker-frontend
   ```

## Useful Commands

### Check all resources:

```bash
kubectl get all -A
```

### Check specific namespace:

```bash
kubectl get all -n default
kubectl get all -n ingress-nginx
```

### Port forward for testing:

```bash
# Test backend directly
kubectl port-forward service/carmodpicker-backend-svc 8000:8000

# Test frontend directly
kubectl port-forward service/carmodpicker-frontend-svc 8080:80
```

### Check ingress controller status:

```bash
kubectl get pods -n ingress-nginx
kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx -f
```

### Test connectivity from within cluster:

```bash
# Create a test pod
kubectl run test-pod --image=busybox --rm -it --restart=Never -- sh

# Test backend connectivity
wget -qO- http://carmodpicker-backend-svc:8000/

# Test frontend connectivity
wget -qO- http://carmodpicker-frontend-svc:80/
```

## Expected URLs

After successful deployment:

- Frontend: http://localhost
- Backend API: http://localhost/api
- Health check: http://localhost/api/ (should return FastAPI docs)

## Environment Variables

Make sure your backend has the correct environment variables:

- Database connection strings
- API keys
- CORS settings

Check the backend configmap and secrets are properly configured.
