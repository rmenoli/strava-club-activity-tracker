# Integration Tests

This directory contains integration tests for the Strava Club Activity Tracker application.

## Setup

### 1. Install Test Dependencies

```bash
uv sync
```

This will install:
- `pytest` - Testing framework
- `pytest-asyncio` - Async test support
- `pytest-env` - Environment variable management
- `httpx` - HTTP client for FastAPI testing

### 2. Set Up Test Database

The tests use a separate PostgreSQL database (`strava_tracker_test`) to avoid affecting your development data.

Make sure PostgreSQL is running:

```bash
docker-compose up -d
```

The test database will be created automatically when you run the tests for the first time.

## Running Tests

### Run All Tests

```bash
pytest
```

### Run Specific Test File

```bash
pytest tests/test_database_integration.py
```

### Run Specific Test Class

```bash
pytest tests/test_database_integration.py::TestAdminDatabase
```

### Run Specific Test

```bash
pytest tests/test_database_integration.py::TestAdminDatabase::test_get_setting
```

### Run with Verbose Output

```bash
pytest -v
```

### Run with Coverage

```bash
pytest --cov=src --cov-report=html
```

## Test Structure

### `conftest.py`
Shared test fixtures and configuration:
- `test_config` - Test configuration with test database URL
- `setup_test_database` - Creates/manages test database
- `admin_db` - AdminDatabase instance with clean state
- `data_db` - StravaDataDatabase instance with clean state
- `mock_strava_client` - Mock Strava API client
- Factory fixtures for creating test data

### `test_database_integration.py`
Database integration tests:
- **TestAdminDatabase** - Tests for settings, location filters, date filters
- **TestStravaDataDatabase** - Tests for athletes, activities, GPS filtering, statistics

## Test Data

The tests use sample data defined in fixtures:
- `sample_athlete` - Basic athlete data
- `sample_activity` - Activity near default location (matches filter)
- `sample_activity_far` - Activity in London (doesn't match default filter)
- `sample_activity_no_gps` - Indoor activity without GPS

## Database Cleanup

Each test automatically cleans up after itself:
- Activities and athletes are deleted after each test
- Settings are reset to defaults
- Date filters are removed

The test database persists between test runs for faster execution. To reset completely:

```bash
# Stop and remove all Docker data
docker-compose down -v

# Restart PostgreSQL
docker-compose up -d
```

## Writing New Tests

1. Add test file in `tests/` directory (must start with `test_`)
2. Use fixtures from `conftest.py`
3. Follow naming convention: `test_description_of_what_is_tested`
4. Clean up test data (fixtures handle this automatically for database tests)

Example:

```python
def test_my_feature(data_db, create_test_athlete):
    """Test description here."""
    athlete_id = create_test_athlete()

    # Your test logic
    result = data_db.some_method(athlete_id)

    assert result is not None
```

## Continuous Integration

To run tests in CI/CD:

1. Ensure PostgreSQL service is available
2. Set environment variables from `.env.test`
3. Run: `pytest --maxfail=5 --tb=short`
