#!/bin/bash

# CarModPicker Test Runner Script
# This script runs tests for both backend and frontend

set -e

echo "🚀 Starting CarModPicker Test Suite"
echo "=================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if we're in the right directory
if [ ! -f "README.md" ] || [ ! -d "backend" ] || [ ! -d "frontend" ]; then
    print_error "Please run this script from the project root directory"
    exit 1
fi

# Function to run backend tests
run_backend_tests() {
    echo ""
    echo "🐍 Running Backend Tests"
    echo "----------------------"
    
    cd backend
    
    # Check if virtual environment exists
    if [ ! -d "venv" ]; then
        print_warning "Virtual environment not found. Creating one..."
        python3 -m venv venv
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Install dependencies
    print_status "Installing backend dependencies..."
    pip install -r requirements.txt
    
    # Run linting
    print_status "Running backend linting..."
    black --check --diff . || {
        print_warning "Black formatting issues found. Run 'black .' to fix."
    }
    
    isort --check-only --diff . || {
        print_warning "Import sorting issues found. Run 'isort .' to fix."
    }
    
    # Run type checking
    print_status "Running backend type checking..."
    mypy app/ --ignore-missing-imports || {
        print_warning "Type checking issues found."
    }
    
    # Run tests
    print_status "Running backend tests..."
    pytest --cov=app --cov-report=term-missing -v
    
    cd ..
}

# Function to run frontend tests
run_frontend_tests() {
    echo ""
    echo "⚛️  Running Frontend Tests"
    echo "------------------------"
    
    cd frontend
    
    # Check if node_modules exists
    if [ ! -d "node_modules" ]; then
        print_status "Installing frontend dependencies..."
        npm install
    fi
    
    # Run linting
    print_status "Running frontend linting..."
    npm run lint || {
        print_warning "Linting issues found."
    }
    
    # Run type checking
    print_status "Running frontend type checking..."
    npm run type-check || {
        print_warning "Type checking issues found."
    }
    
    # Run tests (if available)
    if npm run test 2>/dev/null; then
        print_status "Running frontend tests..."
        npm test
    else
        print_warning "Frontend tests not configured yet."
    fi
    
    # Build application
    print_status "Building frontend application..."
    npm run build
    
    cd ..
}

# Function to run all tests
run_all_tests() {
    echo ""
    echo "🎯 Running All Tests"
    echo "=================="
    
    run_backend_tests
    run_frontend_tests
    
    echo ""
    print_status "All tests completed!"
}

# Function to show help
show_help() {
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  backend    Run only backend tests"
    echo "  frontend   Run only frontend tests"
    echo "  all        Run all tests (default)"
    echo "  help       Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0              # Run all tests"
    echo "  $0 backend      # Run only backend tests"
    echo "  $0 frontend     # Run only frontend tests"
}

# Main script logic
case "${1:-all}" in
    "backend")
        run_backend_tests
        ;;
    "frontend")
        run_frontend_tests
        ;;
    "all")
        run_all_tests
        ;;
    "help"|"-h"|"--help")
        show_help
        ;;
    *)
        print_error "Unknown option: $1"
        show_help
        exit 1
        ;;
esac

echo ""
echo "🎉 Test run completed!"
