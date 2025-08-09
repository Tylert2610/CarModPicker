# CarModPicker

A full-stack application for car enthusiasts to browse cars, discover parts, and build custom modification lists.

## Project Overview

CarModPicker consists of two main components:

- **Backend**: FastAPI-based REST API with PostgreSQL database
- **Frontend**: React/TypeScript SPA with Vite build system

## Quick Start

### Prerequisites

- **Python 3.12+** (for backend)
- **Node.js 18+** (for frontend)
- **Docker & Docker Compose** (for database only)
- **Git** (for version control)

### 1. Clone the Repository

```bash
git clone <repository-url>
cd CarModPicker
```

### 2. Backend Setup

```bash
cd Backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create environment file
cp env.example .env  # Edit with your values

# Start database
docker-compose up -d

# Run migrations
alembic upgrade head

# Start backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend will be available at: http://localhost:8000

### 3. Frontend Setup

```bash
cd ../Frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

Frontend will be available at: http://localhost:5173

## Development Workflow

### Daily Development

1. **Start database**: `cd Backend && docker-compose up -d`
2. **Start backend**: `cd Backend && uvicorn app.main:app --reload`
3. **Start frontend**: `cd Frontend && npm run dev`
4. **Develop**: Both services support hot reload
5. **Stop database**: `cd Backend && docker-compose down`

### Key Features

- **User Authentication**: JWT-based with email verification
- **Car Management**: Browse and manage car information
- **Parts Catalog**: Discover and manage car parts
- **Build Lists**: Create custom modification lists
- **Responsive Design**: Mobile-friendly interface

## Project Structure

```
CarModPicker/
├── Backend/                # FastAPI backend
│   ├── app/               # Application code
│   ├── alembic/           # Database migrations
│   ├── docker-compose.yml # Database services
│   ├── Dockerfile         # Railway deployment
│   └── requirements.txt   # Python dependencies
├── Frontend/              # React frontend
│   ├── src/              # Source code
│   ├── public/           # Static assets
│   ├── Dockerfile        # Railway deployment
│   └── package.json      # Node dependencies
└── README.md             # This file
```

## Technology Stack

### Backend

- **FastAPI** - Modern Python web framework
- **PostgreSQL** - Relational database
- **SQLAlchemy** - ORM and database toolkit
- **Alembic** - Database migration tool
- **Pydantic** - Data validation
- **JWT** - Authentication tokens

### Frontend

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **Tailwind CSS** - Utility-first CSS
- **React Router** - Client-side routing
- **Axios** - HTTP client

### Development Tools

- **Docker** - Database containerization
- **ESLint/Prettier** - Code formatting
- **Pytest** - Backend testing
- **Hot Reload** - Development efficiency

## API Documentation

When the backend is running, visit:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Railway Deployment

Both backend and frontend are configured for Railway deployment:

- **Backend**: See `Backend/RAILWAY_DEPLOYMENT.md`
- **Frontend**: See `Frontend/RAILWAY_DEPLOYMENT.md`

## Development Guidelines

### Backend

- Follow PEP 8 style guidelines
- Use type hints consistently
- Write tests for all endpoints
- Use async/await patterns
- Implement proper error handling

### Frontend

- Use TypeScript for all components
- Follow React hooks patterns
- Implement responsive design
- Use Tailwind CSS for styling
- Write meaningful component names

## Testing

### Backend Testing

```bash
cd Backend
pytest                    # Run all tests
pytest --cov=app         # Run with coverage
```

### Frontend Testing

```bash
cd Frontend
npm run lint             # Check code style
npm run type-check       # Check TypeScript
npm run build            # Test build process
```

## Contributing

1. Create a feature branch
2. Make your changes
3. Test thoroughly
4. Submit a pull request

## Common Issues

### Database Connection

```bash
# Check if database is running
cd Backend && docker-compose ps

# Reset database
cd Backend && docker-compose down -v && docker-compose up -d
```

### Port Conflicts

- Backend uses port 8000
- Frontend uses port 5173
- Database uses port 5432

### Environment Variables

- Backend: Copy `Backend/env.example` to `Backend/.env`
- Frontend: Copy `Frontend/env.example` to `Frontend/.env.local` (optional)

## Getting Help

1. Check the individual README files in Backend/ and Frontend/
2. Review the API documentation at http://localhost:8000/docs
3. Check the troubleshooting sections in component READMEs
4. Create an issue on the project repository

## License

See [LICENSE](./LICENSE) file for details.
