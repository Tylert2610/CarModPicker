#!/usr/bin/env python3
"""
File watcher script to automatically update OpenAPI schema when FastAPI code changes.

This script watches for changes in the FastAPI application code and automatically
updates the OpenAPI schema in the docs folder.
"""

import json
import os
import sys
import time
import requests
from pathlib import Path
from typing import Any, Optional, Set
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class FastAPIChangeHandler(FileSystemEventHandler):
    """Handler for FastAPI file changes."""

    def __init__(self, server_url: str, output_path: str):
        self.server_url = server_url
        self.output_path = output_path
        self.last_update = 0
        self.update_cooldown = 2  # Minimum seconds between updates

    def on_modified(self, event: Any) -> None:
        """Handle file modification events."""
        if event.is_directory:
            return

        # Only watch Python files
        if not event.src_path.endswith(".py"):
            return

        # Skip __pycache__ and other non-source files
        if "__pycache__" in event.src_path or ".pyc" in event.src_path:
            return

        # Rate limiting to avoid too many updates
        current_time = int(time.time())
        if current_time - self.last_update < self.update_cooldown:
            return

        print(f"🔄 Detected change in: {event.src_path}")
        self.update_openapi_schema()
        self.last_update = current_time

    def update_openapi_schema(self) -> None:
        """Update the OpenAPI schema."""
        try:
            # Wait a moment for the server to reload
            time.sleep(1)

            # Fetch the schema
            response = requests.get(f"{self.server_url}/openapi.json", timeout=10)
            response.raise_for_status()
            schema = response.json()

            # Save the schema
            os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
            with open(self.output_path, "w", encoding="utf-8") as f:
                json.dump(schema, f, indent=2, ensure_ascii=False)

            print(f"✅ OpenAPI schema updated: {self.output_path}")

        except Exception as e:
            print(f"❌ Failed to update OpenAPI schema: {e}")


def check_server_running(server_url: str) -> bool:
    """Check if the FastAPI server is running."""
    try:
        response = requests.get(f"{server_url}/health", timeout=5)
        return response.status_code == 200  # type: ignore
    except Exception:
        return False


def main() -> None:
    """Main function to watch for changes and update OpenAPI schema."""
    # Get the project root directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent

    # Define paths
    app_dir = project_root / "backend" / "app"
    output_path = project_root / "docs" / "openapi.json"

    # Get server URL from environment or use default
    server_url = os.getenv("FASTAPI_SERVER_URL", "http://localhost:8000")

    print(f"👀 Starting OpenAPI schema watcher...")
    print(f"📁 Watching: {app_dir}")
    print(f"🌐 Server: {server_url}")
    print(f"📄 Output: {output_path}")

    # Check if server is running
    if not check_server_running(server_url):
        print(f"❌ FastAPI server is not running on {server_url}")
        print("💡 Please start your FastAPI server first:")
        print("   cd backend && python -m uvicorn app.main:app --reload")
        sys.exit(1)

    # Create the event handler
    event_handler = FastAPIChangeHandler(server_url, str(output_path))

    # Create the observer
    observer = Observer()
    observer.schedule(event_handler, str(app_dir), recursive=True)

    # Start watching
    observer.start()
    print("✅ Watcher started! Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping watcher...")
        observer.stop()

    observer.join()


if __name__ == "__main__":
    main()
