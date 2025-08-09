# CarModPicker Backend

A FastAPI-based backend service for the CarModPicker application, providing RESTful APIs for user management, car data, parts, and build lists.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Local Development](#local-development)
- [Database Migrations](#database-migrations)
- [Testing](#testing)
- [Kubernetes Deployment](#kubernetes-deployment)
- [API Documentation](#api-documentation)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

- **Python 3.8+**
- **Docker & Docker Compose** (for containerized development)
- **Kubernetes** (for production deployment)
- **PostgreSQL 16** (database)

### Required Software

- **Git** - for version control
- **kubectl** - for Kubernetes management
- **Docker Desktop** (with Kubernetes enabled for local deployment)

### Environment Files

You need to create the following environment files:

#### `.env` (Main Development)

```bash
# Database Configuration
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=carmodpicker
POSTGRES_HOST=persistant_volume_db
POSTGRES_PORT=5432

# Application Configuration
DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}
ALEMBIC_DATABASE_URL=${DATABASE_URL}

# Security
SECRET_KEY=your_secret_key_here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Email Configuration (for user verification)
SENDGRID_API_KEY=your_sendgrid_api_key
FROM_EMAIL=your_verified_sender@domain.com

# CORS Settings
BACKEND_CORS_ORIGINS=["http://localhost:3000", "http://localhost:5173"]

# Debug Mode
DEBUG=true
```

#### `.env.test` (Testing Environment)

```bash
# Test Database Configuration
POSTGRES_USER=test_user
POSTGRES_PASSWORD=test_password
POSTGRES_DB=carmodpicker_test
POSTGRES_HOST=unit_test_db
POSTGRES_PORT=5432

# Test Application Configuration
DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}
ALEMBIC_DATABASE_URL=${DATABASE_URL}

# Test Security
SECRET_KEY=test_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Test Email Configuration
SENDGRID_API_KEY=test_key
FROM_EMAIL=test@example.com

# Test CORS Settings
BACKEND_CORS_ORIGINS=["http://localhost:3000"]

# Debug Mode
DEBUG=true
```

### Kubernetes Secrets

For production deployment, you'll need to create Kubernetes secrets:

```bash
# Database secrets
kubectl create secret generic postgres-secret \
  --from-literal=POSTGRES_USER=your_db_user \
  --from-literal=POSTGRES_PASSWORD=your_db_password \
  --from-literal=POSTGRES_DB=carmodpicker

# Backend secrets
kubectl create secret generic backend-secret \
  --from-literal=SECRET_KEY=your_secret_key \
  --from-literal=SENDGRID_API_KEY=your_sendgrid_api_key \
  --from-literal=FROM_EMAIL=your_verified_sender@domain.com
```

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd CarModPicker-Backend

# Create environment files
cp .env.example .env  # Edit with your values
cp .env.test.example .env.test  # Edit with your values

# Create Docker network for backend debugging
docker network create carmodpicker_network
```

### 2. Start Services

```bash
# Start all services (backend, production DB, test DB)
docker compose up -d

# Run database migrations
alembic upgrade head

# Start the development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Verify Installation

- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/
- **Database**: PostgreSQL on localhost:5432

## Local Development

### Development Commands

```bash
# Start all services
docker compose up -d

# Run database migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest

# Run tests with coverage
pytest --cov=app

# Check code formatting
black app/
isort app/

# Lint code
flake8 app/
```

### Project Structure

```
app/
├── api/
│   ├── dependencies/     # Authentication and dependencies
│   ├── endpoints/        # API route handlers
│   ├── models/          # SQLAlchemy models
│   ├── schemas/         # Pydantic schemas
│   └── services/        # Business logic
├── core/                # Configuration and core utilities
├── db/                  # Database setup and session management
└── tests/               # Test files
```

### API Endpoints

- **Authentication**: `/api/auth/*`
- **Users**: `/api/users/*`
- **Cars**: `/api/cars/*`
- **Parts**: `/api/parts/*`
- **Build Lists**: `/api/build-lists/*`

## Database Migrations

### Local Development Migrations

#### Creating New Migrations

```bash
# Generate a new migration based on model changes
alembic revision --autogenerate -m "description of changes"

# Create an empty migration file
alembic revision -m "description of changes"
```

#### Running Migrations Locally

```bash
# Apply all pending migrations
alembic upgrade head

# Apply migrations up to a specific revision
alembic upgrade <revision_id>

# Check current migration status
alembic current

# View migration history
alembic history --verbose

# Downgrade to a previous revision
alembic downgrade <revision_id>
```

### Kubernetes Deployment Migrations

The backend deployment includes an init container that automatically runs migrations before the application starts. However, for production environments, it's recommended to run migrations manually.

#### Automatic Migrations (Init Container)

- Migrations run automatically when the deployment starts
- No manual intervention required
- Suitable for development and simple deployments

#### Manual Migrations (Recommended for Production)

##### Using the Migration Script

```bash
cd kubernetes

# Check migration status
./migrate.sh status

# Run migrations manually
./migrate.sh run

# View migration history
./migrate.sh history

# Show help
./migrate.sh help
```

##### Using Kubernetes Jobs Directly

```bash
# Apply the migration job
kubectl apply -f kubernetes/migration-job.yaml

# Monitor the job
kubectl get jobs
kubectl logs job/db-migration-job

# Wait for completion
kubectl wait --for=condition=complete job/db-migration-job --timeout=300s

# Clean up
kubectl delete job db-migration-job
```

#### Migration Workflow for Production

1. **Create and test migrations locally**:

   ```bash
   alembic revision --autogenerate -m "your migration description"
   alembic upgrade head
   ```

2. **Build and push the new image**:

   ```bash
   docker build -t webbpulse/carmodpicker:backend-latest .
   docker push webbpulse/carmodpicker:backend-latest
   ```

3. **Run migrations in production**:

   ```bash
   cd kubernetes
   ./migrate.sh run
   ```

4. **Verify migration status**:

   ```bash
   ./migrate.sh status
   ```

5. **Deploy the application**:
   ```bash
   kubectl rollout restart deployment/carmodpicker-backend
   ```

#### Troubleshooting Migrations

##### Check Migration Status

```bash
# Check current database revision
kubectl run migration-check --rm -i --restart=Never \
  --image=webbpulse/carmodpicker:backend-latest \
  --command -- alembic current

# Check available migrations
kubectl run migration-heads --rm -i --restart=Never \
  --image=webbpulse/carmodpicker:backend-latest \
  --command -- alembic heads
```

##### View Migration Logs

```bash
# View init container logs
kubectl logs deployment/carmodpicker-backend -c db-migrate

# View migration job logs
kubectl logs job/db-migration-job
```

##### Rollback Migrations

```bash
# Create a rollback job
kubectl run migration-rollback --rm -i --restart=Never \
  --image=webbpulse/carmodpicker:backend-latest \
  --command -- alembic downgrade <previous_revision>
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/api/endpoints/test_auth.py

# Run tests with verbose output
pytest -v

# Run tests and stop on first failure
pytest -x
```

### Test Database

The test database runs on port 5433 and is automatically managed by the test suite. It's separate from your development database to ensure test isolation.

### Writing Tests

Tests are organized in the `tests/` directory following the same structure as the main application:

```
tests/
├── api/
│   └── endpoints/       # API endpoint tests
├── dependencies/        # Dependency tests
├── models/             # Model tests
└── conftest.py         # Test configuration and fixtures
```

## Kubernetes Deployment

### Prerequisites

- Kubernetes cluster (local or cloud)
- `kubectl` configured to access your cluster
- Docker images pushed to a registry

### Deployment Scripts

#### Deploy the Application

```bash
cd kubernetes

# Deploy everything (ingress, backend, frontend)
./deploy.sh
```

This script will:

1. Create the `ingress-nginx` namespace
2. Deploy the nginx ingress controller
3. Apply all backend services
4. Apply frontend services
5. Configure ingress routing

#### Clean Up the Deployment

```bash
cd kubernetes

# Remove all deployed resources
./cleanup.sh
```

This script will:

1. Delete ingress configuration
2. Remove frontend and backend services
3. Clean up nginx ingress controller
4. Remove the ingress-nginx namespace

### Manual Deployment

If you prefer to deploy components individually:

```bash
# Deploy nginx ingress controller
kubectl apply -f kubernetes/nginx-ingress-rbac.yaml
kubectl apply -f kubernetes/nginx-ingress-controller.yaml

# Deploy backend services
kubectl apply -f kubernetes/backend-configmap.yaml
kubectl apply -f kubernetes/backend-deployment.yaml
kubectl apply -f kubernetes/backend-service.yaml

# Deploy frontend services
kubectl apply -f ../CarModPicker-Frontend/kubernetes/frontend-deployment.yaml
kubectl apply -f ../CarModPicker-Frontend/kubernetes/frontend-service.yaml

# Deploy ingress
kubectl apply -f kubernetes/ingress.yaml
```

### Accessing the Application

After successful deployment:

- **Frontend**: http://localhost
- **Backend API**: http://localhost/api
- **API Documentation**: http://localhost/api/docs

### Monitoring Deployment

```bash
# Check all resources
kubectl get all -A

# Check specific services
kubectl get services -A

# Check pods
kubectl get pods -A

# Check ingress
kubectl get ingress -A

# View logs
kubectl logs -l app=carmodpicker-backend
kubectl logs -l app=carmodpicker-frontend
```

## API Documentation

### Interactive Documentation

Once the application is running, you can access:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/api/openapi.json

## Troubleshooting

### Common Issues

#### 1. Database Connection Issues

**Symptoms**: Connection refused or authentication errors

**Solutions**:

```bash
# Check if database is running
docker compose ps

# Check database logs
docker compose logs persistant_volume_db

# Verify environment variables
docker compose exec fastapi_backend env | grep POSTGRES
```

#### 2. Migration Issues

**Symptoms**: Migration errors or database schema out of sync

**Solutions**:

```bash
# Check current migration status
alembic current

# Check migration history
alembic history --verbose

# Reset database (WARNING: This will delete all data)
docker compose down -v
docker compose up -d
alembic upgrade head
```

#### 3. Kubernetes Deployment Issues

**Symptoms**: Pods not starting or services not accessible

**Solutions**:

```bash
# Check pod status
kubectl get pods -A

# Check pod logs
kubectl logs <pod-name>

# Check service configuration
kubectl describe service <service-name>

# Check ingress configuration
kubectl describe ingress carmodpicker-ingress
```

### Debugging Commands

#### Local Development

```bash
# Check running containers
docker compose ps

# View logs
docker compose logs -f fastapi_backend

# Access database directly
docker compose exec persistant_volume_db psql -U $POSTGRES_USER -d $POSTGRES_DB

# Test API endpoints
curl http://localhost:8000/
curl http://localhost:8000/docs
```

#### Kubernetes

```bash
# Port forward for direct access
kubectl port-forward service/carmodpicker-backend-svc 8000:8000
kubectl port-forward service/carmodpicker-frontend-svc 8080:80

# Execute commands in pods
kubectl exec -it <pod-name> -- /bin/bash

# Check resource usage
kubectl top pods
kubectl top nodes

# View events
kubectl get events --sort-by='.lastTimestamp'
```

### Performance Monitoring

```bash
# Check application metrics
kubectl logs -l app=carmodpicker-backend | grep -E "(ERROR|WARNING|CRITICAL)"

# Monitor database performance
kubectl exec -it <postgres-pod> -- psql -c "SELECT * FROM pg_stat_activity;"

# Check resource limits
kubectl describe pod <pod-name> | grep -A 5 "Limits:"
```

### Getting Help

1. **Check the logs**: Always start by examining application and system logs
2. **Verify configuration**: Ensure environment variables and secrets are correctly set
3. **Test connectivity**: Use port forwarding to test services directly
4. **Check Kubernetes events**: Look for recent events that might indicate issues
5. **Review the troubleshooting guide**: See `kubernetes/TROUBLESHOOTING.md` for more detailed solutions

For additional help, check the project's issue tracker or documentation.
