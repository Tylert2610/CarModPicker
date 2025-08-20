# CarModPicker Backend

A modern FastAPI backend for the CarModPicker application, providing a robust REST API for car enthusiasts to manage their vehicles, build lists, and parts collections.

## 🏗️ Architecture Overview

The backend follows a clean, modular architecture with clear separation of concerns:

```
backend/
├── app/
│   ├── api/                 # API layer
│   │   ├── endpoints/       # Route handlers
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── schemas/         # Pydantic validation schemas
│   │   ├── dependencies/    # FastAPI dependencies
│   │   └── middleware/      # Custom middleware
│   ├── core/               # Core configuration
│   ├── db/                 # Database setup
│   └── tests/              # Test suite
├── alembic/                # Database migrations
└── requirements.txt        # Dependencies
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 16+
- Docker (optional, for database)

### Development Setup

1. **Clone and navigate to backend**

   ```bash
   cd backend
   ```

2. **Create virtual environment**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Environment configuration**

   ```bash
   cp .env.example .env
   # Edit .env with your database and API settings
   ```

5. **Database setup**

   ```bash
   # Using Docker (recommended)
   docker-compose up -d

   # Or connect to existing PostgreSQL instance
   # Update DATABASE_URL in .env
   ```

6. **Run migrations**

   ```bash
   alembic upgrade head
   ```

7. **Start development server**

   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

8. **Access API documentation**
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

## 📊 Database Models

### Core Entities

#### User Model

```python
class User(Base):
    id: int (Primary Key)
    username: str (Unique, Indexed)
    email: str (Unique, Indexed)
    image_url: Optional[str]
    email_verified: bool (Default: False)
    hashed_password: str
    disabled: bool (Default: False)

    # Relationships
    cars: List[Car] (One-to-Many)
```

#### Car Model

```python
class Car(Base):
    id: int (Primary Key)
    make: str (Indexed)
    model: str (Indexed)
    year: int (Indexed)
    trim: Optional[str] (Indexed)
    vin: Optional[str] (Indexed)
    image_url: Optional[str]
    user_id: int (Foreign Key to User)

    # Relationships
    user: User (Many-to-One)
    build_lists: List[BuildList] (One-to-Many)
```

#### BuildList Model

```python
class BuildList(Base):
    id: int (Primary Key)
    name: str (Indexed)
    description: Optional[str] (Indexed)
    image_url: Optional[str]
    car_id: int (Foreign Key to Car)

    # Relationships
    car: Car (Many-to-One)
    parts: List[Part] (One-to-Many)
```

#### Part Model

```python
class Part(Base):
    id: int (Primary Key)
    name: str (Indexed)
    part_type: Optional[str] (Indexed)
    part_number: Optional[str] (Indexed)
    manufacturer: Optional[str] (Indexed)
    description: Optional[str] (Indexed)
    price: Optional[int] (Indexed)
    image_url: Optional[str]
    build_list_id: int (Foreign Key to BuildList)

    # Relationships
    build_list: BuildList (Many-to-One)
```

## 🔌 API Endpoints

### Authentication (`/api/auth`)

- `POST /login` - User login
- `POST /register` - User registration
- `POST /logout` - User logout
- `POST /verify-email` - Send email verification
- `POST /verify-email/confirm` - Confirm email verification
- `POST /forgot-password` - Request password reset
- `POST /forgot-password/confirm` - Reset password

### Users (`/api/users`)

- `GET /me` - Get current user profile
- `GET /{user_id}` - Get user profile by ID
- `PUT /me` - Update current user profile
- `DELETE /me` - Delete current user account

### Cars (`/api/cars`)

- `GET /` - List cars (with pagination and filtering)
- `POST /` - Create new car
- `GET /{car_id}` - Get car details
- `PUT /{car_id}` - Update car
- `DELETE /{car_id}` - Delete car
- `GET /search` - Search cars by make, model, year

### Build Lists (`/api/build-lists`)

- `GET /` - List build lists (with pagination)
- `POST /` - Create new build list
- `GET /{build_list_id}` - Get build list details
- `PUT /{build_list_id}` - Update build list
- `DELETE /{build_list_id}` - Delete build list

### Parts (`/api/parts`)

- `GET /` - List parts (with pagination and filtering)
- `POST /` - Create new part
- `GET /{part_id}` - Get part details
- `PUT /{part_id}` - Update part
- `DELETE /{part_id}` - Delete part
- `GET /by-build-list/{build_list_id}` - Get parts by build list

## 🔐 Authentication & Authorization

### JWT Token Authentication

- Uses `python-jose` for JWT token generation and validation
- Tokens include user ID and expiration time
- Automatic token refresh mechanism
- Secure password hashing with bcrypt

### Authorization Rules

- Users can only access their own cars, build lists, and parts
- Public read access for user profiles and public builds
- Email verification required for full access
- Rate limiting on all endpoints

## 🛡️ Security Features

### Rate Limiting

- Configurable rate limits per minute and hour
- IP-based rate limiting
- Customizable limits per endpoint

### Input Validation

- Pydantic models for request/response validation
- SQL injection prevention through SQLAlchemy ORM
- XSS protection through proper input sanitization

### CORS Configuration

- Configurable allowed origins
- Secure cookie handling
- Proper CORS headers for frontend integration

## 🧪 Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/api/endpoints/test_cars.py

# Run with verbose output
pytest -v
```

### Test Structure

```
tests/
├── api/
│   └── endpoints/          # API endpoint tests
├── dependencies/           # Dependency tests
├── conftest.py            # Test configuration
└── test_main.py           # Main application tests
```

### Test Database

- Separate test database configuration
- Automatic test data setup and cleanup
- Isolated test environment

## 📝 Code Quality

### Linting and Formatting

```bash
# Format code with Black
black .

# Sort imports with isort
isort .

# Type checking with mypy
mypy .

# Run all quality checks
black . && isort . && mypy .
```

### Pre-commit Hooks

- Automatic code formatting
- Import sorting
- Type checking
- Test execution

## 🗄️ Database Management

### Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1

# View migration history
alembic history
```

### Database Connection

- PostgreSQL with SQLAlchemy 2.0
- Connection pooling for performance
- Automatic connection management
- Health check endpoints

## 🔧 Configuration

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost/carmodpicker

# JWT Authentication
SECRET_KEY=your-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=60

# CORS
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173

# Email (SendGrid)
SENDGRID_API_KEY=your-sendgrid-key
EMAIL_FROM=noreply@carmodpicker.com

# Rate Limiting
ENABLE_RATE_LIMITING=true
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_REQUESTS_PER_HOUR=1000
```

### Development vs Production

- Environment-specific configuration
- Debug mode for development
- Production optimizations
- Railway deployment support

## 🚀 Deployment

### Railway Deployment

The backend is optimized for Railway deployment with:

- Automatic database provisioning
- Environment variable management
- Health check endpoints
- SSL certificate handling

### Docker Deployment

```bash
# Build image
docker build -t carmodpicker-backend .

# Run container
docker run -p 8000:8000 carmodpicker-backend
```

### Health Checks

- `/health` endpoint for monitoring
- Database connection verification
- Service status reporting

## 📚 API Documentation

### Automatic Documentation

- OpenAPI/Swagger specification
- Interactive API documentation
- Request/response examples
- Authentication documentation

### API Versioning

- URL-based versioning (`/api/v1/`)
- Backward compatibility support
- Deprecation notices

## 🔍 Monitoring and Logging

### Logging Configuration

- Structured logging with Python logging
- Different log levels for development/production
- Request/response logging
- Error tracking and reporting

### Performance Monitoring

- Database query optimization
- Response time tracking
- Memory usage monitoring
- Error rate tracking

## 🤝 Contributing

### Development Workflow

1. Create feature branch
2. Write tests for new functionality
3. Implement feature with proper error handling
4. Update documentation
5. Run quality checks
6. Submit pull request

### Code Standards

- Follow PEP 8 style guidelines
- Use type hints throughout
- Write comprehensive docstrings
- Include error handling
- Add tests for new endpoints

## 🆘 Troubleshooting

### Common Issues

- Database connection errors
- Migration conflicts
- CORS issues
- Authentication problems
- Rate limiting

### Debug Mode

```bash
# Enable debug mode
export DEBUG=true
uvicorn app.main:app --reload --log-level debug
```

## 📄 License

This backend is part of the CarModPicker project and is licensed under the MIT License.
