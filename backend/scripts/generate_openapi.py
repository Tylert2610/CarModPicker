#!/usr/bin/env python3
"""
Script to generate and save OpenAPI schema from FastAPI server.

This script fetches the OpenAPI schema from the running FastAPI server
and saves it to the docs folder for easier LLM interpretation and
frontend development reference.
"""

import json
import os
import sys
import requests
from pathlib import Path
from typing import Optional


def get_openapi_schema(base_url: str = "http://localhost:8000") -> Optional[dict]:
    """
    Fetch OpenAPI schema from FastAPI server.

    Args:
        base_url: Base URL of the FastAPI server

    Returns:
        OpenAPI schema as dictionary or None if failed
    """
    try:
        # Try the API-prefixed OpenAPI endpoint
        response = requests.get(f"{base_url}/api/openapi.json", timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Failed to fetch OpenAPI schema from {base_url}/api/openapi.json: {e}")
        return None


def save_openapi_schema(schema: dict, output_path: str) -> bool:
    """
    Save OpenAPI schema to file.

    Args:
        schema: OpenAPI schema dictionary
        output_path: Path to save the schema file

    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure the output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Save with pretty formatting for better readability
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(schema, f, indent=2, ensure_ascii=False)

        print(f"✅ OpenAPI schema saved to: {output_path}")
        return True
    except Exception as e:
        print(f"❌ Failed to save OpenAPI schema: {e}")
        return False


def main():
    """Main function to generate and save OpenAPI schema."""
    # Get the project root directory (two levels up from this script)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent

    # Define output path in the docs folder
    output_path = project_root / "docs" / "openapi.json"

    # Get server URL from environment or use default
    server_url = os.getenv("FASTAPI_SERVER_URL", "http://localhost:8000")

    print(f"🔍 Fetching OpenAPI schema from: {server_url}")

    # Fetch the schema
    schema = get_openapi_schema(server_url)
    if not schema:
        print(
            "❌ Failed to fetch OpenAPI schema. Make sure the FastAPI server is running."
        )
        sys.exit(1)

    # Save the schema
    if save_openapi_schema(schema, str(output_path)):
        print("🎉 OpenAPI schema generation completed successfully!")

        # Print some useful information
        info = schema.get("info", {})
        title = info.get("title", "Unknown API")
        version = info.get("version", "Unknown version")
        paths = schema.get("paths", {})

        print(f"📋 API: {title} v{version}")
        print(f"🔗 Endpoints: {len(paths)}")
        print(f"📁 Saved to: {output_path}")

        # List available tags/endpoint groups
        tags = set()
        for path_data in paths.values():
            for method_data in path_data.values():
                if isinstance(method_data, dict) and "tags" in method_data:
                    tags.update(method_data["tags"])

        if tags:
            print(f"🏷️  Available tags: {', '.join(sorted(tags))}")

    else:
        print("❌ Failed to save OpenAPI schema.")
        sys.exit(1)


if __name__ == "__main__":
    main()
