#!/usr/bin/env python3
"""
Create Admin User Script for CarModPicker API

This script creates an admin user that can be used to create categories and other admin-only operations.

Usage:
    python scripts/create_admin_user.py [--base-url BASE_URL] [--username USERNAME] [--email EMAIL] [--password PASSWORD]
"""

import argparse
import sys
import requests
from urllib.parse import urljoin


def create_admin_user(base_url: str, username: str, email: str, password: str):
    """Create an admin user"""
    print(f"Creating admin user: {username}")
    print(f"Base URL: {base_url}")

    # Create user
    user_data = {"username": username, "email": email, "password": password}

    url = urljoin(base_url.rstrip("/"), "/api/users/")

    try:
        response = requests.post(url, json=user_data)

        if response.status_code == 200:
            user = response.json()
            print(f"✓ Successfully created user: {username} (ID: {user['id']})")
            print(f"Email: {email}")
            print(f"Password: {password}")
            print(
                "\n🔑 You can now login with these credentials to perform admin operations."
            )
            return user
        else:
            print(
                f"✗ Failed to create user {username}: {response.status_code} - {response.text}"
            )
            return None

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Create an admin user for CarModPicker API"
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the CarModPicker API (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--username", default="admin_user", help="Admin username (default: admin_user)"
    )
    parser.add_argument(
        "--email",
        default="admin@example.com",
        help="Admin email (default: admin@example.com)",
    )
    parser.add_argument(
        "--password",
        default="adminpass123",
        help="Admin password (default: adminpass123)",
    )

    args = parser.parse_args()

    try:
        user = create_admin_user(
            args.base_url, args.username, args.email, args.password
        )
        if user:
            print("\n✅ Admin user created successfully!")
        else:
            print("\n❌ Failed to create admin user")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n❌ Admin user creation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Admin user creation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
