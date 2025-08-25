# CarModPicker Project Overview

## Purpose
CarModPicker is a web application for car enthusiasts to manage vehicles, track modifications, and build custom part lists. Users can create profiles, add cars, build modification lists, and share with the community.

## Tech Stack
- **Frontend**: React 19 + TypeScript, Tailwind CSS, Vite
- **Backend**: FastAPI + Python, PostgreSQL, SQLAlchemy ORM
- **Authentication**: JWT tokens with bcrypt
- **Database**: PostgreSQL with Alembic migrations

## User Roles & Permissions
- **Regular Users**: Can manage their own cars, build lists, vote on parts, report issues
- **Admins** (`is_admin=True`): Can manage part reports, view all users, create/edit categories, update user accounts
- **Super Users** (`is_superuser=True`): Have admin privileges plus additional system-level access

## Key Features
- User authentication with email verification
- Car and build list management
- Parts catalog with voting and reporting
- Category system for parts organization
- Subscription tiers (free/premium)