# Test Data Population Script

This script populates the CarModPicker API with comprehensive test data for development and testing purposes.

## Features

- Creates test users with known credentials
- Populates all major database tables:
  - Users
  - Categories (Exhaust, Suspension, Wheels, Engine, Interior)
  - Cars (Honda Civic, Toyota Supra, Subaru WRX STI)
  - Parts (with realistic specifications and pricing)
  - Build Lists (with descriptions and car associations)
  - Build List Parts (parts added to build lists with notes)
  - Votes (upvotes/downvotes on parts)
  - Reports (test reports on parts)

## Prerequisites

1. **Backend API Running**: Ensure your CarModPicker backend API is running
2. **Python Dependencies**: Install the required Python packages

```bash
pip install -r scripts/requirements.txt
```

## Usage

### Basic Usage

```bash
python scripts/populate_test_data.py
```

This will use the default settings:

- API Base URL: `http://localhost:8000`
- Creates 2 test users (testuser1, testuser2)

### Advanced Usage

```bash
python scripts/populate_test_data.py \
  --base-url http://localhost:8000 \
  --admin-email admin@example.com \
  --admin-password adminpass123
```

### Creating Admin Users

If you need to create categories (which require admin privileges), you can create an admin user first:

```bash
python scripts/create_admin_user.py \
  --username admin_user \
  --email admin@example.com \
  --password adminpass123
```

Then run the test data population script with the admin credentials:

```bash
python scripts/populate_test_data.py \
  --admin-email admin@example.com \
  --admin-password adminpass123
```

### Command Line Options

- `--base-url`: Base URL of the CarModPicker API (default: http://localhost:8000)
- `--admin-email`: Admin email for creating an admin test user
- `--admin-password`: Admin password for the admin test user

## Test User Credentials

After running the script, you can login with these test users:

### Regular Users

- **Username**: `testuser1`
- **Password**: `testpass123`
- **Email**: `testuser1@example.com`

- **Username**: `testuser2`
- **Password**: `testpass123`
- **Email**: `testuser2@example.com`

### Admin User (if admin credentials provided)

- **Username**: `admin_user`
- **Password**: `adminpass123` (or the password you provided)
- **Email**: The email you provided

## Created Test Data

### Categories

- Exhaust Systems
- Suspension
- Wheels & Tires
- Engine Performance
- Interior

### Cars (per user)

- 2020 Honda Civic Si
- 2021 Toyota Supra 3.0 Premium
- 2019 Subaru WRX STI Limited

### Parts (per user)

- Invidia N1 Exhaust System ($899)
- Tein Flex Z Coilovers ($1,299)
- Volk TE37 Ultra Wheels ($2,800)
- Hondata FlashPro ($695)
- Recaro Sportster CS Seats ($899)

### Build Lists (per user)

- Daily Driver Build
- Track Day Setup
- Show Car Project

### Additional Data

- Parts added to build lists with notes
- Random votes (upvotes/downvotes) on parts
- Test reports on parts

## Example Output

```
🚀 Starting CarModPicker Test Data Population
Base URL: http://localhost:8000
Test Users: 2

==================================================
POPULATING DATA FOR USER: testuser1
==================================================
Creating user: testuser1
✓ Successfully created user: testuser1 (ID: 1)
Logging in user: testuser1
✓ Successfully logged in user: testuser1

=== Creating Categories ===
✓ Created category: Exhaust Systems (ID: 1)
✓ Created category: Suspension (ID: 2)
✓ Created category: Wheels & Tires (ID: 3)
✓ Created category: Engine Performance (ID: 4)
✓ Created category: Interior (ID: 5)

=== Creating Cars for User 1 ===
✓ Created car: 2020 Honda Civic (ID: 1)
✓ Created car: 2021 Toyota Supra (ID: 2)
✓ Created car: 2019 Subaru WRX STI (ID: 3)

=== Creating Parts for User 1 ===
✓ Created part: Invidia N1 Exhaust System (ID: 1)
✓ Created part: Tein Flex Z Coilovers (ID: 2)
✓ Created part: Volk TE37 Ultra Wheels (ID: 3)
✓ Created part: Hondata FlashPro (ID: 4)
✓ Created part: Recaro Sportster CS Seats (ID: 5)

=== Creating Build Lists for User 1 ===
✓ Created build list: Daily Driver Build (ID: 1)
✓ Created build list: Track Day Setup (ID: 2)
✓ Created build list: Show Car Project (ID: 3)

=== Adding Parts to Build Lists ===
✓ Added part 'Invidia N1 Exhaust System' to build list 'Daily Driver Build'
✓ Added part 'Tein Flex Z Coilovers' to build list 'Daily Driver Build'
✓ Added part 'Volk TE37 Ultra Wheels' to build list 'Daily Driver Build'
...

✓ Completed data population for user: testuser1

============================================================
📊 TEST DATA POPULATION SUMMARY
============================================================

👥 Users Created: 2
  - testuser1 (ID: 1)
  - testuser2 (ID: 2)

📂 Categories Created: 5
  - Exhaust Systems (ID: 1)
  - Suspension (ID: 2)
  - Wheels & Tires (ID: 3)
  - Engine Performance (ID: 4)
  - Interior (ID: 5)

🚗 Cars Created: 6
  - 2020 Honda Civic (ID: 1)
  - 2021 Toyota Supra (ID: 2)
  - 2019 Subaru WRX STI (ID: 3)
  - 2020 Honda Civic (ID: 4)
  - 2021 Toyota Supra (ID: 5)
  - 2019 Subaru WRX STI (ID: 6)

🔧 Parts Created: 10
  - Invidia N1 Exhaust System (ID: 1)
  - Tein Flex Z Coilovers (ID: 2)
  - Volk TE37 Ultra Wheels (ID: 3)
  - Hondata FlashPro (ID: 4)
  - Recaro Sportster CS Seats (ID: 5)
  ...

📋 Build Lists Created: 6
  - Daily Driver Build (ID: 1)
  - Track Day Setup (ID: 2)
  - Show Car Project (ID: 3)
  - Daily Driver Build (ID: 4)
  - Track Day Setup (ID: 5)
  - Show Car Project (ID: 6)

🔗 Build List Parts Created: 18
👍 Votes Created: 15
🚨 Reports Created: 4

============================================================
🔑 TEST USER CREDENTIALS
============================================================
Username: testuser1
Password: testpass123
Email: testuser1@example.com
------------------------------
Username: testuser2
Password: testpass123
Email: testuser2@example.com
------------------------------

✅ Test data population completed successfully!
💡 You can now login with any of the test users above to interact with the created entities.
```

## Troubleshooting

### Common Issues

1. **Connection Refused**: Make sure your backend API is running
2. **Authentication Errors**: Check if the API requires admin privileges for certain operations
3. **Duplicate Key Errors**: The script handles existing data gracefully, but you may see some warnings
4. **Category Creation Fails**: If category creation fails due to admin requirements, the script will automatically use existing categories or create a fallback category

### Error Handling Improvements

The script now includes improved error handling:

- **Graceful Category Handling**: If category creation fails (due to admin requirements), the script will use existing categories
- **Fallback Categories**: If no categories exist, the script creates a fallback "General Parts" category
- **Duplicate User Handling**: The script gracefully handles existing users and continues with the next user
- **Self-Reporting Prevention**: The script handles the case where users cannot report their own parts

### Error Handling

The script includes comprehensive error handling and will:

- Continue processing even if some operations fail
- Provide detailed error messages for debugging
- Show a summary of successful and failed operations

## Development

### Modifying Test Data

To modify the test data, edit the data arrays in the script:

- `categories_data` in `create_categories()`
- `cars_data` in `create_cars()`
- `parts_data` in `create_parts()`
- `build_lists_data` in `create_build_lists()`

### Adding New Entity Types

To add new entity types, follow the pattern of existing methods:

1. Add a new method to create the entities
2. Add the entities to the `created_entities` tracking dictionary
3. Call the method from `populate_data_for_user()`
4. Update the summary in `print_summary()`

## Security Note

This script creates test data with known credentials. **Do not use these credentials in production environments**. The script is intended for development and testing purposes only.
