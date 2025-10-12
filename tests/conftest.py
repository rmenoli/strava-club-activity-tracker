"""Shared test fixtures and configuration for integration tests."""

import json
import pytest
import psycopg2
from datetime import datetime, timedelta
from unittest.mock import Mock
from dotenv import load_dotenv

from src.config import Config
from src.databases.admin_database import AdminDatabase
from src.databases.strava_data_database import StravaDataDatabase
from src.sync_service import ActivitySyncService

# Load test environment variables (override=True ensures test values take precedence)
load_dotenv("tests/.env.test", override=True)


@pytest.fixture(scope="session")
def test_config():
    """Create test configuration.

    Test environment variables are loaded from tests/.env.test at module level,
    so Config() will automatically use test values.
    """
    return Config()


@pytest.fixture(scope="session")
def setup_test_database(test_config):
    """Create test database if it doesn't exist."""
    # Connect to postgres database to create test database
    base_url = test_config.DATABASE_URL.rsplit('/', 1)[0]
    conn = psycopg2.connect(f"{base_url}/postgres")
    conn.autocommit = True
    cursor = conn.cursor()

    try:
        # Drop and recreate test database for clean state
        cursor.execute("DROP DATABASE IF EXISTS strava_tracker_test")
        cursor.execute("CREATE DATABASE strava_tracker_test")
    finally:
        cursor.close()
        conn.close()

    yield

    # Teardown: optionally drop test database after all tests
    # Uncomment if you want to clean up after tests
    # conn = psycopg2.connect(f"{base_url}/postgres")
    # conn.autocommit = True
    # cursor = conn.cursor()
    # cursor.execute("DROP DATABASE IF EXISTS strava_tracker_test")
    # cursor.close()
    # conn.close()


@pytest.fixture
def admin_db(test_config, setup_test_database):
    """Create AdminDatabase instance with clean state for each test."""
    db = AdminDatabase(test_config.DATABASE_URL)
    yield db

    # Cleanup: clear all data after each test
    with db.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM date_location_filters")
            # Reset settings to defaults
            cursor.execute("""
                UPDATE settings SET value = '90' WHERE key = 'activity_filter_days';
                UPDATE settings SET value = '5' WHERE key = 'discount_threshold_activities';
                UPDATE settings SET value = '50.097416' WHERE key = 'target_latitude';
                UPDATE settings SET value = '14.462274' WHERE key = 'target_longitude';
                UPDATE settings SET value = '1.0' WHERE key = 'filter_radius_km';
            """)
            conn.commit()


@pytest.fixture
def data_db(test_config, setup_test_database):
    """Create StravaDataDatabase instance with clean state for each test."""
    db = StravaDataDatabase(test_config.DATABASE_URL)
    yield db

    # Cleanup: clear all data after each test
    with db.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM activities")
            cursor.execute("DELETE FROM athletes")
            conn.commit()


@pytest.fixture
def sync_service(data_db, test_config):
    """Create ActivitySyncService instance."""
    return ActivitySyncService(data_db, test_config)


@pytest.fixture
def mock_strava_client():
    """Create a mock Strava client for testing without real API calls."""
    mock_client = Mock()
    mock_client.access_token = "test_access_token"
    mock_client.refresh_token = "test_refresh_token"
    mock_client.expires_at = int((datetime.now() + timedelta(hours=6)).timestamp())
    mock_client.athlete_id = "12345"

    # Mock token exchange
    mock_client.exchange_code_for_tokens = Mock(return_value="12345")

    # Mock ensure valid token (no refresh needed)
    mock_client.ensure_valid_token = Mock()

    # Mock fetch activities with sample data
    mock_client.fetch_all_activities = Mock(return_value=[])

    return mock_client


@pytest.fixture
def sample_athlete():
    """Sample athlete data for testing."""
    return {
        "athlete_id": "12345",
        "first_name": "Test",
        "last_name": "Athlete",
    }


@pytest.fixture
def sample_activity():
    """Sample activity data with GPS coordinates."""
    return {
        "id": 1001,
        "name": "Morning Run",
        "type": "Run",
        "start_date": "2025-10-10T08:00:00Z",
        "distance": 5000.0,
        "moving_time": 1800,
        "elapsed_time": 1900,
        "total_elevation_gain": 50.0,
        "start_latlng": [50.097416, 14.462274],  # Near default location
        "end_latlng": [50.098000, 14.463000],    # Near default location
    }


@pytest.fixture
def sample_activity_far():
    """Sample activity data with GPS coordinates far from default location."""
    return {
        "id": 1002,
        "name": "Evening Run",
        "type": "Run",
        "start_date": "2025-10-11T18:00:00Z",
        "distance": 7000.0,
        "moving_time": 2400,
        "elapsed_time": 2500,
        "total_elevation_gain": 80.0,
        "start_latlng": [51.5074, -0.1278],  # London - far from default
        "end_latlng": [51.5080, -0.1280],
    }


@pytest.fixture
def sample_activity_no_gps():
    """Sample activity data without GPS coordinates."""
    return {
        "id": 1003,
        "name": "Indoor Bike",
        "type": "VirtualRide",
        "start_date": "2025-10-12T10:00:00Z",
        "distance": 15000.0,
        "moving_time": 3600,
        "elapsed_time": 3600,
        "total_elevation_gain": 0.0,
        "start_latlng": None,
        "end_latlng": None,
    }


@pytest.fixture
def create_test_athlete(data_db):
    """Factory fixture to create test athletes."""
    def _create_athlete(athlete_id="12345", first_name="Test", last_name="Athlete"):
        data_db.upsert_athlete(athlete_id, first_name, last_name)
        return athlete_id
    return _create_athlete


@pytest.fixture
def create_test_activity(data_db):
    """Factory fixture to create test activities."""
    def _create_activity(athlete_id, activity_data):
        """Insert activity with raw_data containing GPS coordinates."""
        with data_db.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO activities (
                        activity_id, athlete_id, name, type, start_date,
                        distance, moving_time, elapsed_time, total_elevation_gain,
                        average_speed, max_speed, raw_data
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (activity_id) DO NOTHING
                """, (
                    activity_data["id"],
                    athlete_id,
                    activity_data["name"],
                    activity_data["type"],
                    activity_data["start_date"],
                    activity_data["distance"],
                    activity_data["moving_time"],
                    activity_data["elapsed_time"],
                    activity_data.get("total_elevation_gain", 0),
                    activity_data.get("distance", 0) / activity_data.get("moving_time", 1),
                    activity_data.get("distance", 0) / activity_data.get("moving_time", 1) * 1.5,
                    json.dumps(activity_data),  # Store full data as JSON string
                ))
                conn.commit()
        return activity_data["id"]
    return _create_activity


@pytest.fixture
def create_date_filter(admin_db):
    """Factory fixture to create date-specific location filters."""
    def _create_filter(date_str, latitude, longitude, radius_km=1.0, description="Test filter"):
        admin_db.add_date_location_filter(date_str, latitude, longitude, radius_km, description)
        return date_str
    return _create_filter
