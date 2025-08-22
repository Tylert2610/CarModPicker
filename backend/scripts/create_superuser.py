#!/usr/bin/env python3
"""
Script to create the first superuser for the CarModPicker application.
This script should be run once to set up the initial admin user.
"""

import sys
import os
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy.orm import Session
from app.api.dependencies.auth import get_password_hash
from app.api.models.user import User
from app.db.session import get_db


def create_superuser(
    username: str,
    email: str,
    password: str,
    is_superuser: bool = True,
    is_admin: bool = True,
) -> User:
    """
    Create a superuser in the database.

    Args:
        username: The username for the superuser
        email: The email for the superuser
        password: The password for the superuser
        is_superuser: Whether the user should be a superuser
        is_admin: Whether the user should be an admin

    Returns:
        The created User object
    """
    db = next(get_db())

    try:
        # Check if user already exists
        existing_user = (
            db.query(User)
            .filter((User.username == username) | (User.email == email))
            .first()
        )

        if existing_user:
            print(f"User with username '{username}' or email '{email}' already exists.")
            return existing_user

        # Create the superuser
        hashed_password = get_password_hash(password)

        superuser = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            is_superuser=is_superuser,
            is_admin=is_admin,
            email_verified=True,  # Auto-verify superuser email
            disabled=False,
        )

        db.add(superuser)
        db.commit()
        db.refresh(superuser)

        print(f"✅ Superuser '{username}' created successfully!")
        print(f"   Email: {email}")
        print(f"   Superuser: {is_superuser}")
        print(f"   Admin: {is_admin}")

        return superuser

    except Exception as e:
        db.rollback()
        print(f"❌ Error creating superuser: {e}")
        raise
    finally:
        db.close()


def main() -> None:
    """Main function to run the superuser creation script."""
    print("🚀 CarModPicker Superuser Creation Script")
    print("=" * 50)

    # Get user input
    username = input("Enter username for superuser: ").strip()
    if not username:
        print("❌ Username is required!")
        return

    email = input("Enter email for superuser: ").strip()
    if not email:
        print("❌ Email is required!")
        return

    password = input("Enter password for superuser: ").strip()
    if not password:
        print("❌ Password is required!")
        return

    confirm_password = input("Confirm password: ").strip()
    if password != confirm_password:
        print("❌ Passwords do not match!")
        return

    # Ask about privileges
    print("\nPrivileges:")
    is_superuser = input("Make superuser? (y/N): ").strip().lower() in ["y", "yes"]
    is_admin = input("Make admin? (y/N): ").strip().lower() in ["y", "yes"]

    if not is_superuser and not is_admin:
        print("❌ User must have at least admin privileges!")
        return

    print(f"\nCreating superuser with the following details:")
    print(f"Username: {username}")
    print(f"Email: {email}")
    print(f"Superuser: {is_superuser}")
    print(f"Admin: {is_admin}")

    confirm = input("\nProceed? (y/N): ").strip().lower()
    if confirm not in ["y", "yes"]:
        print("❌ Superuser creation cancelled.")
        return

    try:
        create_superuser(username, email, password, is_superuser, is_admin)
        print("\n🎉 Superuser creation completed successfully!")
        print("You can now log in to the application with these credentials.")

    except Exception as e:
        print(f"\n❌ Failed to create superuser: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
