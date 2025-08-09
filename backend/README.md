# CarModPicker Backend

A FastAPI-based backend service for the CarModPicker application, providing RESTful APIs for user management, car data, parts, and build lists.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Local Development](#local-development)
- [Database Migrations](#database-migrations)
- [Testing](#testing)
- [Railway Deployment](#railway-deployment)
- [API Documentation](#api-documentation)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

- **Python 3.12+**
- **Docker & Docker Compose** (for database only)
- **PostgreSQL 16** (database via Docker)

### Required Software

- **Git** - for version control
- **Python virtual environment** - for dependency isolation

### Environment Files

You need to create the following environment files:

#### `.env` (Main Development)

```bash
# Database Configuration (for Docker)
POSTGRES_USER=carmodpicker_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=carmodpicker
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Application Configuration
DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}

# Security
SECRET_KEY=your_secret_key_here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Email Configuration (for user verification)
SENDGRID_API_KEY=your_sendgrid_api_key
EMAIL_FROM=your_verified_sender@domain.com
SENDGRID_VERIFY_EMAIL_TEMPLATE_ID=your_template_id
SENDGRID_RESET_PASSWORD_TEMPLATE_ID=your_template_id

# CORS Settings
ALLOWED_ORIGINS=["http://localhost:3000", "http://localhost:5173"]

# Debug Mode
DEBUG=true
```

#### `.env.test` (Testing Environment)

```bash
# Test Database Configuration
POSTGRES_USER=test_user
POSTGRES_PASSWORD=test_password
POSTGRES_DB=carmodpicker_test
POSTGRES_HOST=localhost
POSTGRES_PORT=5433

# Test Application Configuration
DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}

# Test Security
SECRET_KEY=test_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Test Email Configuration
SENDGRID_API_KEY=test_key
EMAIL_FROM=test@example.com
SENDGRID_VERIFY_EMAIL_TEMPLATE_ID=test_template
SENDGRID_RESET_PASSWORD_TEMPLATE_ID=test_template

# Test CORS Settings
ALLOWED_ORIGINS=["http://localhost:3000"]

# Debug Mode
DEBUG=true
```

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd CarModPicker/Backend

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create environment files
cp env.example .env  # Edit with your values
cp env.example .env.test  # Edit with your test values
```

### 2. Start Database Services

```bash
# Start only the databases (dev and test)
docker-compose up -d

# Verify databases are running
docker-compose ps
```

### 3. Run Database Migrations

```bash
# Run migrations
alembic upgrade head
```

### 4. Start Development Server

```bash
# Start the FastAPI backend directly on host
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Verify Installation

- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/
- **Database**: PostgreSQL on localhost:5432

## Local Development

### Development Workflow

```bash
# 1. Start databases
docker-compose up -d

# 2. Activate virtual environment
source venv/bin/activate

# 3. Run migrations (if needed)
alembic upgrade head

# 4. Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 5. In another terminal, run tests
pytest

# 6. Stop databases when done
docker-compose down
```

### Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest

# Run tests with coverage
pytest --cov=app --cov-report=html

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

### Creating New Migrations

```bash
# Generate a new migration based on model changes
alembic revision --autogenerate -m "description of changes"

# Create an empty migration file
alembic revision -m "description of changes"
```

### Running Migrations

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

## Railway Deployment

For production deployment to Railway, see [RAILWAY_DEPLOYMENT.md](./RAILWAY_DEPLOYMENT.md) for detailed instructions.

### Quick Railway Setup

1. Connect your GitHub repo to Railway
2. Add PostgreSQL database service
3. Configure environment variables (see Railway deployment guide)
4. Deploy - migrations run automatically

## API Documentation

### Interactive Documentation

Once the application is running, you can access:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Troubleshooting

### Common Issues

#### 1. Database Connection Issues

**Symptoms**: Connection refused or authentication errors

**Solutions**:

```bash
# Check if database is running
docker-compose ps

# Check database logs
docker-compose logs persistant_volume_db

# Verify environment variables
env | grep POSTGRES
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
docker-compose down -v
docker-compose up -d
alembic upgrade head
```

#### 3. Virtual Environment Issues

**Symptoms**: Module not found or import errors

**Solutions**:

```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt

# Check Python path
which python
```

### Debugging Commands

```bash
# Check running containers
docker-compose ps

# View database logs
docker-compose logs -f persistant_volume_db

# Access database directly
docker-compose exec persistant_volume_db psql -U carmodpicker_user -d carmodpicker

# Test API endpoints
curl http://localhost:8000/
curl http://localhost:8000/docs

# Check if port is in use
lsof -i :8000
```

### Performance Monitoring

```bash
# Check Python process
ps aux | grep python

# Monitor database connections
docker-compose exec persistant_volume_db psql -U carmodpicker_user -d carmodpicker -c "SELECT * FROM pg_stat_activity;"

# Check application logs
tail -f app.log  # if logging to file
```

### Getting Help

1. **Check the logs**: Always start by examining application logs
2. **Verify configuration**: Ensure environment variables are correctly set
3. **Test connectivity**: Verify database connection
4. **Check dependencies**: Ensure all packages are installed
5. **Review the Railway deployment guide**: For production deployment issues

For additional help, check the project's issue tracker or documentation.
