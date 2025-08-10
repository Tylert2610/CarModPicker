# CI Workflows and Rate Limiting Implementation

This document explains the CI/CD workflows and rate limiting implementation for the CarModPicker project.

## CI/CD Workflows

### Backend CI Workflow (`.github/workflows/backend-ci.yml`)

The backend CI workflow runs on:

- Push to `main` or `develop` branches (when backend files change)
- Pull requests to `main` or `develop` branches (when backend files change)

**What it does:**

1. **Environment Setup**: Uses Ubuntu latest with Python 3.11
2. **Database Service**: Spins up PostgreSQL 15 for testing
3. **Dependencies**: Installs Python dependencies including testing tools
4. **Code Quality Checks**:
   - **Black**: Code formatting check
   - **isort**: Import sorting check
   - **MyPy**: Type checking
5. **Testing**: Runs pytest with coverage reporting
6. **Coverage Upload**: Uploads coverage reports to Codecov

**Required Environment Variables for Testing:**

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/test_db
SECRET_KEY=test-secret-key-for-ci
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
ALLOWED_ORIGINS=http://localhost:3000
DEBUG=true
PROJECT_NAME=CarModPicker API
API_STR=/api/v1
SENDGRID_API_KEY=test-key
FROM_EMAIL=test@example.com
```

### Frontend CI Workflow (`.github/workflows/frontend-ci.yml`)

The frontend CI workflow runs on:

- Push to `main` or `develop` branches (when frontend files change)
- Pull requests to `main` or `develop` branches (when frontend files change)

**What it does:**

1. **Environment Setup**: Uses Ubuntu latest with Node.js 18
2. **Dependencies**: Installs npm dependencies
3. **Code Quality Checks**:
   - **ESLint**: Code linting
   - **TypeScript**: Type checking
4. **Build Verification**: Builds the application and tests the output
5. **Build Testing**: Serves the built application and verifies it's accessible

## Rate Limiting Implementation

### Overview

The rate limiting system is implemented as FastAPI middleware to prevent abuse of the API. It's designed for small web applications with limited users.

### Features

- **Per-IP Rate Limiting**: Tracks requests by client IP address
- **Dual Time Windows**:
  - Per-minute limit (default: 60 requests)
  - Per-hour limit (default: 1000 requests)
- **Proxy Support**: Handles X-Forwarded-For headers for proxy setups
- **Automatic Cleanup**: Removes old requests to prevent memory leaks
- **Health Check Exclusion**: Skips rate limiting for health checks and documentation

### Configuration

The rate limiter is configured in `backend/app/api/middleware/rate_limiter.py`:

```python
# Default limits
requests_per_minute = 60
requests_per_hour = 1000
```

### Rate Limit Headers

The middleware adds the following headers to responses:

- `X-RateLimit-Remaining-Minute`: Remaining requests in current minute
- `X-RateLimit-Remaining-Hour`: Remaining requests in current hour
- `X-RateLimit-Reset-Minute`: Seconds until minute window resets
- `X-RateLimit-Reset-Hour`: Seconds until hour window resets

### Rate Limit Response

When rate limited, the API returns:

```json
{
  "detail": "Too many requests",
  "message": "Rate limit exceeded: 61 requests per minute",
  "retry_after": 60
}
```

With HTTP status code 429 and headers:

- `Retry-After: 60`
- `X-RateLimit-Limit-Minute: 60`
- `X-RateLimit-Limit-Hour: 1000`

### Implementation Details

**File Structure:**

```
backend/app/api/middleware/
├── __init__.py
├── rate_limiter.py
└── test_rate_limiter.py
```

**Key Components:**

1. **RateLimiter Class**: Core rate limiting logic
2. **rate_limit_middleware**: FastAPI middleware function
3. **Client IP Detection**: Handles both direct and proxy connections
4. **Memory Management**: Automatic cleanup of old request timestamps

### Testing

Rate limiting is thoroughly tested with unit tests covering:

- Rate limiter initialization
- Client IP detection (direct and proxy)
- Minute and hour rate limiting
- Request cleanup
- Middleware integration
- Header generation

Run tests with:

```bash
cd backend
pytest app/tests/test_rate_limiter.py -v
```

## Setup Instructions

### Backend Setup

1. **Install Development Dependencies:**

```bash
cd backend
pip install -r requirements.txt
```

2. **Run Linting:**

```bash
black --check --diff .
isort --check-only --diff .
```

3. **Run Type Checking:**

```bash
mypy app/ --ignore-missing-imports
```

4. **Run Tests:**

```bash
pytest --cov=app --cov-report=term-missing
```

### Frontend Setup

1. **Install Dependencies:**

```bash
cd frontend
npm install
```

2. **Run Linting:**

```bash
npm run lint
```

3. **Run Type Checking:**

```bash
npm run type-check
```

4. **Run Tests:**

```bash
npm test
```

5. **Build Application:**

```bash
npm run build
```

## Configuration Files

### Backend Configuration

- **`pyproject.toml`**: Black, isort, and MyPy configuration
- **`pytest.ini`**: Pytest configuration with coverage settings
- **`requirements.txt`**: Python dependencies including testing tools

### Frontend Configuration

- **`vitest.config.ts`**: Vitest testing configuration
- **`package.json`**: NPM scripts and dependencies
- **`src/test/setup.ts`**: Test environment setup

## Monitoring and Maintenance

### Rate Limiting Monitoring

Monitor rate limiting effectiveness by checking:

- 429 response rates in your application logs
- Rate limit header values in API responses
- Memory usage of the rate limiter (for large-scale deployments)

### CI/CD Monitoring

Monitor CI/CD effectiveness by:

- Checking workflow success rates in GitHub Actions
- Reviewing test coverage reports
- Monitoring build times and resource usage

### Production Considerations

For production deployments:

1. **Consider Redis**: Replace in-memory rate limiting with Redis for multi-instance deployments
2. **Adjust Limits**: Tune rate limits based on your application's needs
3. **Monitoring**: Add metrics collection for rate limiting events
4. **Whitelisting**: Consider whitelisting trusted IPs or API keys

## Troubleshooting

### Common Issues

1. **Rate Limiting Too Aggressive**: Adjust limits in `RateLimiter` initialization
2. **CI Tests Failing**: Check environment variables and database connectivity
3. **Type Checking Errors**: Review MyPy configuration and add type hints
4. **Linting Failures**: Run `black` and `isort` to auto-format code

### Debugging Rate Limiting

To debug rate limiting issues:

1. Check the `X-RateLimit-*` headers in API responses
2. Review application logs for rate limiting warnings
3. Test with different IP addresses to verify per-IP tracking
4. Monitor memory usage for potential leaks

## Security Considerations

1. **IP Spoofing**: The rate limiter trusts X-Forwarded-For headers
2. **Memory Usage**: In-memory storage may not scale for large deployments
3. **Bypass Attempts**: Consider additional security measures for critical endpoints
4. **Monitoring**: Log rate limiting events for security analysis
