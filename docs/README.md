# CarModPicker

A comprehensive web application for car enthusiasts to manage their vehicles, track modifications, and build custom part lists. CarModPicker provides a modern, user-friendly interface for organizing car builds and sharing them with the community.

## 🚗 Features

### Core Functionality

- **User Authentication**: Secure registration, login, and email verification
- **Car Management**: Add, edit, and organize your vehicle collection
- **Build Lists**: Create custom modification plans for specific cars
- **Parts Catalog**: Track parts, prices, and compatibility
- **User Profiles**: Share your builds and view other enthusiasts' work
- **Search & Filter**: Find cars and parts with advanced filtering options

### Technical Features

- **Modern Web Stack**: React frontend with FastAPI backend
- **Real-time Updates**: Live data synchronization
- **Responsive Design**: Works seamlessly on desktop and mobile
- **Secure API**: JWT authentication with rate limiting
- **Database Management**: PostgreSQL with automated migrations
- **Docker Support**: Easy deployment and development setup

## 🏗️ Architecture

CarModPicker follows a modern microservices architecture with clear separation of concerns:

```
CarModPicker/
├── frontend/          # React TypeScript application
├── backend/           # FastAPI Python application
└── scripts/           # Development and deployment utilities
```

### Frontend (React + TypeScript)

- **Framework**: React 19 with TypeScript
- **Styling**: Tailwind CSS for responsive design
- **Routing**: React Router for navigation
- **State Management**: React Context for authentication
- **Testing**: Vitest with React Testing Library
- **Build Tool**: Vite for fast development

### Backend (FastAPI + Python)

- **Framework**: FastAPI with async support
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Authentication**: JWT tokens with bcrypt password hashing
- **API Documentation**: Automatic OpenAPI/Swagger generation
- **Testing**: Pytest with comprehensive test coverage
- **Migrations**: Alembic for database schema management

## 🚀 Quick Start

### Prerequisites

- Node.js 18+ and npm
- Python 3.11+
- PostgreSQL 16+
- Docker (optional, for database)

### Development Setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/yourusername/CarModPicker.git
   cd CarModPicker
   ```

2. **Backend Setup**

   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt

   # Set up environment variables
   cp .env.example .env
   # Edit .env with your database and API settings

   # Start PostgreSQL (using Docker)
   docker-compose up -d

   # Run migrations
   alembic upgrade head

   # Start the backend server
   uvicorn app.main:app --reload
   ```

3. **Frontend Setup**

   ```bash
   cd frontend
   npm install

   # Start the development server
   npm run dev
   ```

4. **Access the application**
   - Frontend: http://localhost:4000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

## 📁 Project Structure

### Backend Structure

```
backend/
├── app/
│   ├── api/
│   │   ├── endpoints/     # API route handlers
│   │   ├── models/        # SQLAlchemy database models
│   │   ├── schemas/       # Pydantic request/response models
│   │   └── dependencies/  # FastAPI dependencies
│   ├── core/              # Configuration and utilities
│   ├── db/                # Database setup and sessions
│   └── tests/             # Test suite
├── alembic/               # Database migrations
└── requirements.txt       # Python dependencies
```

### Frontend Structure

```
frontend/
├── src/
│   ├── components/        # Reusable UI components
│   │   ├── auth/         # Authentication components
│   │   ├── cars/         # Car management components
│   │   ├── parts/        # Parts catalog components
│   │   ├── buildLists/   # Build list components
│   │   └── common/       # Shared UI components
│   ├── pages/            # Page components
│   ├── contexts/         # React context providers
│   ├── services/         # API service layer
│   └── types/            # TypeScript type definitions
├── public/               # Static assets
└── package.json          # Node.js dependencies
```

## 🗄️ Database Schema

The application uses a relational database with the following core entities:

- **Users**: Authentication and profile information
- **Cars**: Vehicle information (make, model, year, VIN)
- **Build Lists**: Custom modification plans linked to cars
- **Parts**: Individual components with pricing and compatibility

## 🔧 Development

### Running Tests

```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm test
```

### Code Quality

```bash
# Backend linting and formatting
cd backend
black .
isort .
mypy .

# Frontend linting
cd frontend
npm run lint
```

### Database Migrations

```bash
cd backend
# Create a new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback migrations
alembic downgrade -1
```

## 🚀 Deployment

### Production Deployment

The application is designed for deployment on Railway with:

- Automatic database provisioning
- Environment variable management
- SSL certificate handling
- Health check endpoints

### Environment Variables

Key environment variables for production:

- `DATABASE_URL`: PostgreSQL connection string
- `SECRET_KEY`: JWT signing secret
- `ALLOWED_ORIGINS`: CORS allowed origins
- `SENDGRID_API_KEY`: Email service configuration

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow the established code style and conventions
- Write tests for new features
- Update documentation as needed
- Use conventional commit messages
- Ensure all tests pass before submitting PRs

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

For support and questions:

- Create an issue on GitHub
- Check the API documentation at `/docs` when running locally
- Review the individual README files in `frontend/` and `backend/` directories

## 🔮 Roadmap

- [ ] Advanced search and filtering
- [ ] Social features (likes, comments, sharing)
- [ ] Mobile app development
- [ ] Integration with parts suppliers
- [ ] Build cost tracking and budgeting
- [ ] Performance analytics and recommendations
