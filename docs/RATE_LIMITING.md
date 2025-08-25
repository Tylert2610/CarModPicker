# Sophisticated Rate Limiting

The CarModPicker API now uses a sophisticated rate limiting system that provides different rate limits based on HTTP methods and endpoint types.

## Overview

The rate limiter decouples rate limits for different types of requests:

- **GET requests**: Higher limits for read operations
- **POST/PUT/DELETE requests**: Lower limits for write operations
- **Authentication endpoints**: Very low limits to prevent brute force attacks
- **Admin endpoints**: Moderate limits for administrative operations

## Configuration

Rate limits can be configured via environment variables:

```bash
# General rate limits (for POST/PUT/DELETE requests)
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_REQUESTS_PER_HOUR=1000

# GET request rate limits (higher for read operations)
RATE_LIMIT_GET_REQUESTS_PER_MINUTE=120
RATE_LIMIT_GET_REQUESTS_PER_HOUR=2000

# Authentication endpoint rate limits (lower to prevent abuse)
RATE_LIMIT_AUTH_REQUESTS_PER_MINUTE=10
RATE_LIMIT_AUTH_REQUESTS_PER_HOUR=100

# Admin endpoint rate limits
RATE_LIMIT_ADMIN_REQUESTS_PER_MINUTE=30
RATE_LIMIT_ADMIN_REQUESTS_PER_HOUR=300
```

## Rate Limit Types

### 1. GET Requests

- **Path**: Any endpoint with GET method
- **Default**: 120 requests/minute, 2000 requests/hour
- **Use case**: Browsing cars, parts, build lists, etc.

### 2. Authentication Endpoints

- **Path**: `/api/auth/*`
- **Default**: 10 requests/minute, 100 requests/hour
- **Use case**: Login, registration, password reset

### 3. Admin Endpoints

- **Path**: `/api/admin/*` or any path containing "admin"
- **Default**: 30 requests/minute, 300 requests/hour
- **Use case**: Administrative operations

### 4. Default (Write Operations)

- **Path**: Any POST/PUT/DELETE request not covered above
- **Default**: 60 requests/minute, 1000 requests/hour
- **Use case**: Creating/updating/deleting cars, parts, build lists

## Response Headers

The API includes rate limit information in response headers:

```
X-RateLimit-Limit-Minute: 120
X-RateLimit-Limit-Hour: 2000
X-RateLimit-Remaining-Minute: 115
X-RateLimit-Remaining-Hour: 1985
X-RateLimit-Reset-Minute: 45
X-RateLimit-Reset-Hour: 3540
```

## Rate Limit Exceeded Response

When rate limits are exceeded, the API returns:

```json
{
  "detail": "Too many requests",
  "message": "Rate limit exceeded: 121 requests per minute",
  "retry_after": 60,
  "limits": {
    "minute_limit": 120,
    "hour_limit": 2000,
    "minute_count": 121,
    "hour_count": 150
  }
}
```

With headers:

```
Retry-After: 60
X-RateLimit-Limit-Minute: 120
X-RateLimit-Limit-Hour: 2000
X-RateLimit-Remaining-Minute: 0
X-RateLimit-Remaining-Hour: 1850
```

## Exempted Endpoints

The following endpoints are exempt from rate limiting:

- `/` (root)
- `/health` (health check)
- `/docs` (API documentation)
- `/openapi.json` (OpenAPI schema)
- `/redoc` (ReDoc documentation)

## Implementation Details

- Uses in-memory storage for rate limiting (suitable for small to medium applications)
- Automatically cleans up old request timestamps
- Handles proxy headers (X-Forwarded-For) for proper client IP detection
- Separate tracking for each rate limit type to prevent interference

## Production Considerations

For production deployments with multiple instances, consider:

1. **Redis-based rate limiting**: Replace in-memory storage with Redis
2. **Distributed rate limiting**: Use a service like Cloudflare or AWS WAF
3. **Monitoring**: Track rate limit violations and adjust limits accordingly
4. **User-based limits**: Implement per-user rate limits for authenticated users

## Testing

Rate limiting is disabled in test environments by default. To enable it for testing:

```bash
ENABLE_RATE_LIMITING=true
```

## Migration from Previous Version

The new rate limiter is backward compatible. Existing applications will automatically benefit from the improved rate limiting without any code changes.
