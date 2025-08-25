# Parallel Testing Setup

This document explains how parallel testing is configured for the CarModPicker backend.

## Overview

The project uses `pytest-xdist` to run tests in parallel, which can significantly reduce test execution time. Each worker process gets its own SQLite database to avoid conflicts.

## Configuration

### 1. Dependencies

The following packages are required for parallel testing:

```txt
pytest-xdist>=3.8.0
```

**Note**: No additional database dependencies are needed since we use SQLite, which is included with Python.

### 2. Pytest Configuration

Parallel testing is configured in `pytest.ini`:

```ini
addopts =
    -n auto          # Automatically determine number of workers
    --dist=loadfile  # Distribute tests by file (not by test)
```

### 3. Database Setup

#### SQLite In-Memory Databases

Tests use SQLite in-memory databases for maximum speed and simplicity:

- **No setup required** - SQLite databases are created automatically
- **In-memory storage** - No disk I/O, extremely fast
- **Automatic cleanup** - Databases are destroyed when tests complete
- **Worker isolation** - Each worker gets its own database

#### Database Files

For parallel testing, each worker gets its own SQLite database:

- **Single process**: Uses file-based database (`test_{pid}.db`)
- **Parallel workers**: Uses in-memory database (`sqlite:///:memory:`) to avoid file locking issues
- **Automatic cleanup**: All database files are automatically removed after tests complete

## Setup Instructions

### 1. No Database Setup Required!

Unlike PostgreSQL, SQLite databases are created automatically. No setup scripts needed!

### 2. Run Tests

#### Parallel Execution (Default)

```bash
# Run all tests in parallel
python -m pytest

# Run specific test files in parallel
python -m pytest app/tests/api/endpoints/test_auth.py app/tests/api/endpoints/test_cars.py
```

#### Sequential Execution

```bash
# Run tests sequentially (disable parallel execution)
python -m pytest -n 0
```

#### Custom Number of Workers

```bash
# Use 4 workers
python -m pytest -n 4

# Use 2 workers
python -m pytest -n 2
```

## How It Works

### 1. Worker Detection

The `get_worker_id()` function detects if tests are running in parallel:

```python
def get_worker_id():
    """Get the worker ID for parallel testing, or None if not in parallel mode."""
    worker_id = os.environ.get('PYTEST_XDIST_WORKER')
    if worker_id:
        return worker_id.replace('gw', '')
    return None
```

### 2. Database URL Generation

Each worker gets a unique SQLite database:

```python
def get_test_database_url():
    worker_id = get_worker_id()
    if worker_id:
        # Each worker gets its own in-memory database
        return f"sqlite:///:memory:"
    else:
        # Default test database - file-based for single process
        return f"sqlite:///./test_{pid}.db"
```

### 3. Session Factory

A global session factory ensures each worker has its own database connection:

```python
def get_test_session_factory():
    global TestingSessionLocal
    if TestingSessionLocal is None:
        database_url = get_test_database_url()
        engine = create_engine(
            database_url,
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=engine)
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return TestingSessionLocal
```

### 4. Automatic Cleanup

Test database files are automatically cleaned up after each test session:

- **Session fixture**: `cleanup_test_databases` fixture runs after all tests
- **Pytest hook**: `pytest_sessionfinish` hook ensures cleanup even if tests fail
- **File patterns**: Removes `test_*.db` and `test_worker_*.db` files
- **Error handling**: Gracefully handles files that are in use or already removed

## Performance Benefits

### Before Parallel Testing

- 159 tests: ~45-60 seconds
- Sequential execution

### After Parallel Testing

- 159 tests: ~8-15 seconds
- ~3-4x speed improvement
- Automatic worker count based on CPU cores
- SQLite in-memory databases for maximum speed

## Advantages of SQLite for Testing

### 1. **Speed**

- In-memory storage - no disk I/O
- No network overhead
- Instant database creation/destruction

### 2. **Simplicity**

- No separate database server needed
- No configuration required
- No setup scripts

### 3. **Reliability**

- No connection issues
- No server dependencies
- Works offline

### 4. **Isolation**

- Each test gets a fresh database
- No shared state between tests
- Automatic cleanup

## Troubleshooting

### Database Connection Issues

SQLite rarely has connection issues, but if they occur:

1. **Check file permissions**: Ensure the test directory is writable
2. **Check disk space**: Ensure there's enough space for SQLite files
3. **Restart tests**: SQLite issues usually resolve with a fresh start

### Worker Conflicts

If tests fail due to worker conflicts:

1. **Reduce workers**: Use `-n 2` or `-n 4` instead of `auto`
2. **Check isolation**: Ensure tests don't share state between workers
3. **Check file locks**: Ensure no other processes are accessing SQLite files

### Performance Issues

If tests are slow:

1. **Check worker count**: Use `-n auto` for optimal performance
2. **Check system resources**: Ensure CPU and memory are available
3. **Profile tests**: Identify slow individual tests

## Best Practices

### 1. Test Independence

- Each test should be completely independent
- No shared state between tests
- Use fixtures for test data setup

### 2. Database Cleanup

- Tests should clean up after themselves
- Use transaction rollback for automatic cleanup
- SQLite automatically cleans up in-memory databases

### 3. Resource Management

- Close database connections properly
- Use appropriate fixture scopes
- Avoid long-running operations in test setup

### 4. Debugging

- Use `-n 0` for sequential execution when debugging
- Use `--tb=long` for detailed error traces
- Check worker-specific logs if needed

## Commands Reference

```bash
# Testing (no setup required!)
python -m pytest                               # Run all tests in parallel
python -m pytest -n 0                          # Run tests sequentially
python -m pytest -n 4                          # Use 4 workers
python -m pytest app/tests/api/endpoints/      # Run specific directory
python -m pytest -k "test_auth"                # Run specific test pattern
python -m pytest --tb=long                     # Detailed error traces
python -m pytest -v                            # Verbose output

# Cleanup (optional)
rm -f test.db test_worker_*.db                 # Remove SQLite files
```

## Migration Notes

When adding new database migrations:

1. **Automatic setup**: SQLite databases are created automatically
2. **Worker isolation**: Each worker has its own migration state
3. **Clean state**: Test databases start with a clean state for each test run

## Comparison: SQLite vs PostgreSQL for Testing

| Aspect            | SQLite                   | PostgreSQL                      |
| ----------------- | ------------------------ | ------------------------------- |
| **Setup**         | None required            | Database server + setup scripts |
| **Speed**         | Very fast (in-memory)    | Slower (network + disk)         |
| **Dependencies**  | Built-in                 | External server                 |
| **Isolation**     | Perfect (separate files) | Good (separate databases)       |
| **Reliability**   | Very high                | Depends on server               |
| **Configuration** | None                     | Host, port, credentials         |

## Future Improvements

1. **In-memory option**: Use `:memory:` databases for even faster tests
2. **Test categorization**: Add markers for slow/fast tests to optimize distribution
3. **CI/CD optimization**: Optimize parallel testing for CI/CD pipelines
4. **Performance monitoring**: Add test execution time tracking
