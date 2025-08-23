#!/bin/bash

# Script to update OpenAPI schema from FastAPI server
# This script fetches the latest OpenAPI schema and saves it to docs/openapi.json

set -e  # Exit on any error

# Get the project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🚀 Updating OpenAPI schema..."

# Check if FastAPI server is running
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "❌ FastAPI server is not running on http://localhost:8000"
    echo "💡 Please start your FastAPI server first:"
    echo "   cd backend && python -m uvicorn app.main:app --reload"
    exit 1
fi

# Run the Python script to generate OpenAPI schema
cd "$PROJECT_ROOT/backend"
python scripts/generate_openapi.py

echo "✅ OpenAPI schema updated successfully!"
echo "📁 Schema saved to: $PROJECT_ROOT/docs/openapi.json"
