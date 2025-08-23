# OpenAPI Schema Automation

This document describes the automated OpenAPI schema generation system for the CarModPicker project.

## Overview

The OpenAPI schema is automatically generated from your FastAPI server and saved to `docs/openapi.json` for easier LLM interpretation and frontend development reference.

## Quick Start

### Manual Update

To manually update the OpenAPI schema:

```bash
# From the project root
./scripts/update-openapi.sh
```

### Automatic Watching

To automatically update the schema when you make changes to your FastAPI code:

```bash
# From the project root
./scripts/watch-openapi.sh
```

## How It Works

### 1. Manual Update Script (`scripts/update-openapi.sh`)

- Checks if the FastAPI server is running
- Fetches the OpenAPI schema from `http://localhost:8000/openapi.json`
- Saves it to `docs/openapi.json` with pretty formatting
- Provides useful information about the API

### 2. Automatic Watcher (`scripts/watch-openapi.sh`)

- Watches for changes in the `backend/app/` directory
- Automatically updates the schema when Python files are modified
- Includes rate limiting to prevent excessive updates
- Requires the `watchdog` Python package

## Prerequisites

1. **FastAPI Server Running**: Your FastAPI server must be running on `http://localhost:8000`
2. **Dependencies**: The `watchdog` package is required for automatic watching

## Installation

The required dependencies are already included in `backend/requirements.txt`. To install:

```bash
cd backend
pip install -r requirements.txt
```

## Usage Examples

### Development Workflow

1. **Start your FastAPI server**:

   ```bash
   cd backend
   python -m uvicorn app.main:app --reload
   ```

2. **Start the OpenAPI watcher** (in a separate terminal):

   ```bash
   ./scripts/watch-openapi.sh
   ```

3. **Make changes to your FastAPI code** - the schema will automatically update!

### One-time Update

If you just want to update the schema once:

```bash
./scripts/update-openapi.sh
```

### Custom Server URL

You can specify a custom server URL using environment variables:

```bash
export FASTAPI_SERVER_URL="http://localhost:8001"
./scripts/update-openapi.sh
```

## File Structure

```
CarModPicker/
├── scripts/
│   ├── update-openapi.sh          # Manual update script
│   └── watch-openapi.sh           # Automatic watcher script
├── backend/
│   └── scripts/
│       ├── generate_openapi.py    # Python script for manual updates
│       └── watch_and_update_openapi.py  # Python watcher script
└── docs/
    └── openapi.json               # Generated OpenAPI schema
```

## Benefits

1. **LLM-Friendly**: The schema is saved in a readable format for better LLM interpretation
2. **Frontend Development**: Frontend developers can reference the latest API schema
3. **Documentation**: Always up-to-date API documentation
4. **Automation**: No manual steps required during development
5. **Version Control**: Schema changes are tracked in git

## Troubleshooting

### Server Not Running

```
❌ FastAPI server is not running on http://localhost:8000
💡 Please start your FastAPI server first:
   cd backend && python -m uvicorn app.main:app --reload
```

### Watchdog Not Installed

The watcher script will automatically install the `watchdog` package if it's missing.

### Permission Denied

Make sure the scripts are executable:

```bash
chmod +x scripts/update-openapi.sh
chmod +x scripts/watch-openapi.sh
```

### Schema Not Updating

- Check that your FastAPI server is running
- Verify the server URL is correct
- Check the console output for error messages

## Integration with Development Workflow

### VS Code Integration

You can add these scripts to your VS Code tasks:

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Update OpenAPI Schema",
      "type": "shell",
      "command": "./scripts/update-openapi.sh",
      "group": "build"
    },
    {
      "label": "Watch OpenAPI Schema",
      "type": "shell",
      "command": "./scripts/watch-openapi.sh",
      "group": "build",
      "isBackground": true
    }
  ]
}
```

### Git Hooks

You can add a pre-commit hook to ensure the schema is always up-to-date:

```bash
# .git/hooks/pre-commit
#!/bin/bash
./scripts/update-openapi.sh
git add docs/openapi.json
```

## Advanced Configuration

### Custom Output Path

You can modify the Python scripts to save the schema to a different location.

### Multiple Environments

You can use different server URLs for different environments:

```bash
# Development
export FASTAPI_SERVER_URL="http://localhost:8000"

# Staging
export FASTAPI_SERVER_URL="https://staging-api.carmodpicker.com"

# Production
export FASTAPI_SERVER_URL="https://api.carmodpicker.com"
```

## Contributing

When adding new endpoints or modifying existing ones:

1. The schema will automatically update if you're using the watcher
2. If not, run `./scripts/update-openapi.sh` manually
3. Commit the updated `docs/openapi.json` file

This ensures that the API documentation stays in sync with your code changes.
