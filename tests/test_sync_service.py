"""Unit tests for ActivitySyncService logic."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock

from src.sync_service import ActivitySyncService


class TestActivitySyncService:
    """Test suite for ActivitySyncService business logic."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database instance."""
        db = Mock()
        db.needs_sync = Mock()
        db.get_latest_activity_date = Mock()
        db.get_activities = Mock()
        db.save_activities = Mock()
        db.save_athlete_tokens = Mock()
        db.get_athlete_tokens = Mock()
        return db

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration instance."""
        config = Mock()
        config.STRAVA_CLIENT_ID = 'test_client_id'
        config.STRAVA_CLIENT_SECRET = 'test_client_secret'
        config.STRAVA_REDIRECT_URI = 'http://localhost:8000/auth/strava/callback'
        return config

    @pytest.fixture
    def mock_strava_client(self):
        """Create a mock Strava client."""
        client = Mock()
        client.access_token = 'test_access_token'
        client.refresh_token = 'test_refresh_token'
        client.expires_at = int((datetime.now() + timedelta(hours=6)).timestamp())
        client.get_all_activities = Mock(return_value=[])
        return client

    @pytest.fixture
    def sync_service(self, mock_db, mock_config):
        """Create ActivitySyncService instance with mocked dependencies."""
        return ActivitySyncService(mock_db, mock_config)

    # ===== get_sync_start_date() Tests =====

    def test_get_sync_start_date_first_time_sync(self, sync_service, mock_db):
        """Test get_sync_start_date returns 180 days ago for first-time sync."""
        # Setup: No activities exist (first-time sync)
        mock_db.get_latest_activity_date.return_value = None

        # Execute
        sync_start_date = sync_service.get_sync_start_date('12345')

        # Verify: Should return approximately 180 days ago
        expected_date = datetime.now() - timedelta(days=180)
        assert sync_start_date is not None
        assert isinstance(sync_start_date, datetime)

        # Check it's within 1 minute of expected (to account for test execution time)
        time_diff = abs((sync_start_date - expected_date).total_seconds())
        assert time_diff < 60, f"Expected ~180 days ago, got {time_diff} seconds difference"

        # Verify database was queried
        mock_db.get_latest_activity_date.assert_called_once_with('12345')

    def test_get_sync_start_date_subsequent_sync(self, sync_service, mock_db):
        """Test get_sync_start_date returns latest activity date minus 1 day for subsequent sync."""
        # Setup: Latest activity exists
        latest_activity_date = datetime(2025, 10, 15, 12, 0, 0)
        mock_db.get_latest_activity_date.return_value = latest_activity_date

        # Execute
        sync_start_date = sync_service.get_sync_start_date('12345')

        # Verify: Should return latest activity date minus 1 day
        expected_date = latest_activity_date - timedelta(days=1)
        assert sync_start_date == expected_date
        assert sync_start_date == datetime(2025, 10, 14, 12, 0, 0)

        # Verify database was queried
        mock_db.get_latest_activity_date.assert_called_once_with('12345')

    def test_get_sync_start_date_with_recent_activity(self, sync_service, mock_db):
        """Test get_sync_start_date with very recent activity (yesterday)."""
        # Setup: Activity from yesterday
        yesterday = datetime.now() - timedelta(days=1)
        mock_db.get_latest_activity_date.return_value = yesterday

        # Execute
        sync_start_date = sync_service.get_sync_start_date('12345')

        # Verify: Should return 2 days ago (yesterday - 1 day)
        expected_date = yesterday - timedelta(days=1)
        assert sync_start_date == expected_date

    # ===== should_sync() Tests =====

    def test_should_sync_when_sync_needed(self, sync_service, mock_db):
        """Test should_sync returns True when sync is needed."""
        # Setup: Database indicates sync is needed
        mock_db.needs_sync.return_value = True

        # Execute
        result = sync_service.should_sync('12345')

        # Verify
        assert result is True
        mock_db.needs_sync.assert_called_once_with('12345', max_age_hours=1)

    def test_should_sync_when_data_is_fresh(self, sync_service, mock_db):
        """Test should_sync returns False when data is fresh."""
        # Setup: Database indicates sync is not needed
        mock_db.needs_sync.return_value = False

        # Execute
        result = sync_service.should_sync('12345')

        # Verify
        assert result is False
        mock_db.needs_sync.assert_called_once_with('12345', max_age_hours=1)

    # ===== sync_athlete_activities() Tests =====

    def test_sync_athlete_activities_successful_sync(
        self, sync_service, mock_db, mock_strava_client
    ):
        """Test successful activity sync returns correct result structure."""
        # Setup
        athlete_id = '12345'
        mock_db.needs_sync.return_value = True
        mock_db.get_latest_activity_date.return_value = datetime(2025, 10, 10)
        mock_db.save_activities.return_value = 5  # 5 new activities
        mock_db.get_activities.return_value = ['act1', 'act2', 'act3', 'act4', 'act5']
        mock_strava_client.get_all_activities.return_value = [
            {'id': 1}, {'id': 2}, {'id': 3}, {'id': 4}, {'id': 5}
        ]

        # Execute
        result = sync_service.sync_athlete_activities(athlete_id, mock_strava_client)

        # Verify result structure
        assert isinstance(result, dict)
        assert result['athlete_id'] == athlete_id
        assert result['synced'] is True
        assert result['new_activities'] == 5
        assert result['total_activities'] == 5
        assert result['error'] is None
        assert 'sync_from_date' in result
        assert 'message' in result

        # Verify database interactions
        mock_db.needs_sync.assert_called_once()
        mock_db.save_activities.assert_called_once()
        mock_db.save_athlete_tokens.assert_called_once()

    def test_sync_athlete_activities_when_sync_not_needed(
        self, sync_service, mock_db, mock_strava_client
    ):
        """Test sync skipped when data is fresh."""
        # Setup
        athlete_id = '12345'
        mock_db.needs_sync.return_value = False
        mock_db.get_activities.return_value = ['existing_activity']

        # Execute
        result = sync_service.sync_athlete_activities(athlete_id, mock_strava_client)

        # Verify
        assert result['athlete_id'] == athlete_id
        assert result['synced'] is False
        assert result['new_activities'] == 0
        assert result['total_activities'] == 1
        assert result['error'] is None
        assert 'Sync not needed' in result['message']

        # Verify Strava API was NOT called
        mock_strava_client.get_all_activities.assert_not_called()

    def test_sync_athlete_activities_handles_exceptions(
        self, sync_service, mock_db, mock_strava_client
    ):
        """Test that exceptions during sync are captured in result."""
        # Setup
        athlete_id = '12345'
        mock_db.needs_sync.return_value = True
        mock_db.get_latest_activity_date.side_effect = Exception("Database error")

        # Execute
        result = sync_service.sync_athlete_activities(athlete_id, mock_strava_client)

        # Verify error is captured
        assert result['athlete_id'] == athlete_id
        assert result['synced'] is False
        assert result['error'] is not None
        assert 'Database error' in result['error']

    def test_sync_athlete_activities_saves_tokens_after_sync(
        self, sync_service, mock_db, mock_strava_client
    ):
        """Test that OAuth tokens are saved to database after successful sync."""
        # Setup
        athlete_id = '12345'
        mock_db.needs_sync.return_value = True
        mock_db.get_latest_activity_date.return_value = datetime(2025, 10, 10)
        mock_db.save_activities.return_value = 3
        mock_db.get_activities.return_value = ['act1', 'act2', 'act3']

        # Execute
        sync_service.sync_athlete_activities(athlete_id, mock_strava_client)

        # Verify tokens were saved
        mock_db.save_athlete_tokens.assert_called_once_with(
            athlete_id,
            mock_strava_client.access_token,
            mock_strava_client.refresh_token,
            mock_strava_client.expires_at
        )

    # ===== sync_athlete_with_stored_tokens() Tests =====

    def test_sync_with_stored_tokens_no_tokens_found(self, sync_service, mock_db):
        """Test sync with stored tokens when no tokens exist in database."""
        # Setup
        athlete_id = '12345'
        mock_db.get_athlete_tokens.return_value = None

        # Execute
        result = sync_service.sync_athlete_with_stored_tokens(athlete_id)

        # Verify
        assert result['athlete_id'] == athlete_id
        assert result['synced'] is False
        assert result['error'] == 'No stored tokens found for athlete'

    def test_sync_with_stored_tokens_successful_load(self, sync_service, mock_db):
        """Test that stored tokens are loaded and used for sync."""
        # Setup
        athlete_id = '12345'
        stored_tokens = {
            'access_token': 'stored_access_token',
            'refresh_token': 'stored_refresh_token',
            'expires_at': int((datetime.now() + timedelta(hours=6)).timestamp())
        }
        mock_db.get_athlete_tokens.return_value = stored_tokens
        mock_db.needs_sync.return_value = False
        mock_db.get_activities.return_value = []

        # Execute
        result = sync_service.sync_athlete_with_stored_tokens(athlete_id)

        # Verify tokens were loaded
        mock_db.get_athlete_tokens.assert_called_once_with(athlete_id)

        # Verify result structure
        assert result['athlete_id'] == athlete_id
        assert 'synced' in result

    # ===== Result Structure Tests =====

    def test_sync_result_has_all_required_fields(self, sync_service, mock_db, mock_strava_client):
        """Test that sync result always contains required fields."""
        # Setup
        athlete_id = '12345'
        mock_db.needs_sync.return_value = False
        mock_db.get_activities.return_value = []

        # Execute
        result = sync_service.sync_athlete_activities(athlete_id, mock_strava_client)

        # Verify all required fields exist
        assert 'athlete_id' in result
        assert 'synced' in result
        assert 'new_activities' in result
        assert 'total_activities' in result
        assert 'error' in result

        # Verify types
        assert isinstance(result['athlete_id'], str)
        assert isinstance(result['synced'], bool)
        assert isinstance(result['new_activities'], int)
        assert isinstance(result['total_activities'], int)
