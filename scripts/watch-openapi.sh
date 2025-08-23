#!/bin/bash

# Script to start OpenAPI schema watcher
# This script watches for changes in FastAPI code and automatically updates the OpenAPI schema

set -e  # Exit on any error

# Get the project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "👀 Starting OpenAPI schema watcher..."

# Check if FastAPI server is running
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "❌ FastAPI server is not running on http://localhost:8000"
    echo "💡 Please start your FastAPI server first:"
    echo "   cd backend && python -m uvicorn app.main:app --reload"
    exit 1
fi

# Check if watchdog is installed
if ! python -c "import watchdog" 2>/dev/null; then
    echo "📦 Installing watchdog dependency..."
    cd "$PROJECT_ROOT/backend"
    pip install watchdog
fi

# Run the watcher script
cd "$PROJECT_ROOT/backend"
python scripts/watch_and_update_openapi.py
