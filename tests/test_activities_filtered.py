"""Integration tests for get_activities_filtered method."""

import pytest


class TestGetActivitiesFiltered:
    """Test suite for StravaDataDatabase.get_activities_filtered()"""

    def test_basic_retrieval_without_admin_db(
        self, data_db, create_test_athlete, create_test_activity, sample_activity
    ):
        """Test basic activity retrieval without location filtering."""
        # Setup: Create athlete and activity
        athlete_id = create_test_athlete()
        create_test_activity(athlete_id, sample_activity)

        # Execute: Get activities without admin_db (no location filtering)
        activities = data_db.get_activities_filtered(athlete_id, admin_db=None)

        # Verify
        assert len(activities) == 1
        activity = activities[0]

        # Check basic fields
        assert activity["activity_id"] == sample_activity["id"]
        assert activity["athlete_id"] == athlete_id
        assert activity["name"] == sample_activity["name"]
        assert activity["type"] == sample_activity["type"]
        assert activity["distance"] == sample_activity["distance"]

        # Check extracted GPS fields
        assert activity["start_latlng"] == sample_activity["start_latlng"]
        assert activity["end_latlng"] == sample_activity["end_latlng"]

        # Verify no location filtering applied
        assert "matches_location_filter" not in activity
        assert "filter_info" not in activity

    def test_location_filtering_with_default_settings_match(
        self,
        data_db,
        admin_db,
        create_test_athlete,
        create_test_activity,
        sample_activity,
    ):
        """Test location filtering with activity that matches default location."""
        # Setup: Create athlete and activity near default location (Prague)
        athlete_id = create_test_athlete()
        create_test_activity(athlete_id, sample_activity)

        # Execute: Get activities with admin_db (enables location filtering)
        activities = data_db.get_activities_filtered(athlete_id, admin_db=admin_db)

        # Verify
        assert len(activities) == 1
        activity = activities[0]

        # Check location filtering was applied
        assert "matches_location_filter" in activity
        assert "filter_info" in activity

        # Activity should match (it's near Prague default location)
        assert activity["matches_location_filter"] is True

        # Check filter info structure
        filter_info = activity["filter_info"]
        assert "target_location" in filter_info
        assert "radius_km" in filter_info
        assert "source" in filter_info
        assert "start_distance_km" in filter_info
        assert "end_distance_km" in filter_info

        # Verify it used default settings
        assert filter_info["source"] == "default"

        # Distances should be small (within 1km)
        assert filter_info["start_distance_km"] < 1.0
        assert filter_info["end_distance_km"] < 1.0

    def test_location_filtering_with_default_settings_no_match(
        self,
        data_db,
        admin_db,
        create_test_athlete,
        create_test_activity,
        sample_activity_far,
    ):
        """Test location filtering with activity that doesn't match default location."""
        # Setup: Create athlete and activity far from default location (London)
        athlete_id = create_test_athlete()
        create_test_activity(athlete_id, sample_activity_far)

        # Execute
        activities = data_db.get_activities_filtered(athlete_id, admin_db=admin_db)

        # Verify
        assert len(activities) == 1
        activity = activities[0]

        # Check location filtering was applied
        assert "matches_location_filter" in activity
        assert "filter_info" in activity

        # Activity should NOT match (it's in London, far from Prague)
        assert activity["matches_location_filter"] is False

        # Check filter info
        filter_info = activity["filter_info"]
        assert filter_info["source"] == "default"

        # Distances should be large (>1000km)
        assert filter_info["start_distance_km"] > 1000.0
        assert filter_info["end_distance_km"] > 1000.0

    def test_location_filtering_without_gps_data(
        self,
        data_db,
        admin_db,
        create_test_athlete,
        create_test_activity,
    ):
        """Test location filtering with activity that has no GPS coordinates."""
        # Setup: Create athlete and Run activity without GPS (e.g., treadmill run)
        athlete_id = create_test_athlete()

        # Create a Run activity without GPS coordinates
        treadmill_run = {
            "id": 1003,
            "name": "Treadmill Run",
            "type": "Run",  # Must be Run type to be returned by the query
            "start_date": "2025-10-12T10:00:00Z",
            "distance": 5000.0,
            "moving_time": 1800,
            "elapsed_time": 1800,
            "total_elevation_gain": 0.0,
            "start_latlng": None,
            "end_latlng": None,
        }
        create_test_activity(athlete_id, treadmill_run)

        # Execute
        activities = data_db.get_activities_filtered(athlete_id, admin_db=admin_db)

        # Verify
        assert len(activities) == 1
        activity = activities[0]

        # Check location filtering fields
        assert "matches_location_filter" in activity
        assert "filter_info" in activity

        # Activity should not match (no GPS data)
        assert activity["matches_location_filter"] is False
        assert activity["filter_info"] is None

        # GPS fields should be None
        assert activity["start_latlng"] is None
        assert activity["end_latlng"] is None

    def test_location_filtering_with_date_specific_override(
        self,
        data_db,
        admin_db,
        create_test_athlete,
        create_test_activity,
        create_date_filter,
    ):
        """Test location filtering with date-specific location override."""
        # Setup: Create athlete and activity
        athlete_id = create_test_athlete()

        # Create activity on specific date
        activity_data = {
            "id": 2001,
            "name": "Special Event Run",
            "type": "Run",
            "start_date": "2025-10-10T08:00:00Z",
            "distance": 5000.0,
            "moving_time": 1800,
            "elapsed_time": 1900,
            "total_elevation_gain": 50.0,
            "start_latlng": [51.5074, -0.1278],  # London coordinates
            "end_latlng": [51.5080, -0.1280],
        }
        create_test_activity(athlete_id, activity_data)

        # Create date-specific filter for that date, centered on London
        create_date_filter(
            "2025-10-10",
            latitude=51.5074,  # London
            longitude=-0.1278,
            radius_km=1.0,
            description="London event",
        )

        # Execute
        activities = data_db.get_activities_filtered(athlete_id, admin_db=admin_db)

        # Verify
        assert len(activities) == 1
        activity = activities[0]

        # Activity should match (date-specific filter centered on London)
        assert activity["matches_location_filter"] is True

        # Check it used date-specific filter
        filter_info = activity["filter_info"]
        assert filter_info["source"] == "date_specific"
        assert filter_info["filter_date"] == "2025-10-10"

        # Distances should be small (within London area)
        assert filter_info["start_distance_km"] < 1.0
        assert filter_info["end_distance_km"] < 1.0

    def test_multiple_activities_ordering(
        self,
        data_db,
        admin_db,
        create_test_athlete,
        create_test_activity,
    ):
        """Test that multiple activities are returned in correct order (DESC by date)."""
        # Setup: Create athlete
        athlete_id = create_test_athlete()

        # Create activities with different dates
        activity1 = {
            "id": 3001,
            "name": "Run 1",
            "type": "Run",
            "start_date": "2025-10-10T08:00:00Z",
            "distance": 5000.0,
            "moving_time": 1800,
            "elapsed_time": 1900,
            "total_elevation_gain": 50.0,
            "start_latlng": [50.097416, 14.462274],
            "end_latlng": [50.098000, 14.463000],
        }
        activity2 = {
            "id": 3002,
            "name": "Run 2",
            "type": "Run",
            "start_date": "2025-10-12T08:00:00Z",  # Later date
            "distance": 7000.0,
            "moving_time": 2400,
            "elapsed_time": 2500,
            "total_elevation_gain": 80.0,
            "start_latlng": [50.097416, 14.462274],
            "end_latlng": [50.098000, 14.463000],
        }
        activity3 = {
            "id": 3003,
            "name": "Run 3",
            "type": "Run",
            "start_date": "2025-10-11T08:00:00Z",  # Middle date
            "distance": 6000.0,
            "moving_time": 2100,
            "elapsed_time": 2200,
            "total_elevation_gain": 60.0,
            "start_latlng": [50.097416, 14.462274],
            "end_latlng": [50.098000, 14.463000],
        }

        create_test_activity(athlete_id, activity1)
        create_test_activity(athlete_id, activity2)
        create_test_activity(athlete_id, activity3)

        # Execute
        activities = data_db.get_activities_filtered(athlete_id, admin_db=admin_db)

        # Verify: Should return 3 activities in DESC order by date
        assert len(activities) == 3
        assert activities[0]["activity_id"] == 3002  # Latest (2025-10-12)
        assert activities[1]["activity_id"] == 3003  # Middle (2025-10-11)
        assert activities[2]["activity_id"] == 3001  # Earliest (2025-10-10)

    def test_limit_parameter(
        self, data_db, create_test_athlete, create_test_activity
    ):
        """Test that limit parameter correctly restricts number of results."""
        # Setup: Create athlete and multiple activities
        athlete_id = create_test_athlete()

        for i in range(5):
            activity = {
                "id": 4000 + i,
                "name": f"Run {i}",
                "type": "Run",
                "start_date": f"2025-10-{10+i:02d}T08:00:00Z",
                "distance": 5000.0,
                "moving_time": 1800,
                "elapsed_time": 1900,
                "total_elevation_gain": 50.0,
                "start_latlng": [50.097416, 14.462274],
                "end_latlng": [50.098000, 14.463000],
            }
            create_test_activity(athlete_id, activity)

        # Execute: Get activities with limit
        activities = data_db.get_activities_filtered(athlete_id, limit=3)

        # Verify: Should return only 3 activities
        assert len(activities) == 3

    def test_empty_result_for_nonexistent_athlete(self, data_db, admin_db):
        """Test that querying for non-existent athlete returns empty list."""
        # Execute: Query for athlete that doesn't exist
        activities = data_db.get_activities_filtered(
            "nonexistent_athlete", admin_db=admin_db
        )

        # Verify: Should return empty list
        assert activities == []

    def test_filters_only_run_activities(
        self, data_db, create_test_athlete, create_test_activity
    ):
        """Test that only 'Run' type activities are returned."""
        # Setup: Create athlete
        athlete_id = create_test_athlete()

        # Create a Run activity
        run_activity = {
            "id": 5001,
            "name": "Morning Run",
            "type": "Run",
            "start_date": "2025-10-10T08:00:00Z",
            "distance": 5000.0,
            "moving_time": 1800,
            "elapsed_time": 1900,
            "total_elevation_gain": 50.0,
            "start_latlng": [50.097416, 14.462274],
            "end_latlng": [50.098000, 14.463000],
        }

        # Note: The create_test_activity will insert the activity as-is
        # The filter is applied at query time in get_activities_filtered
        create_test_activity(athlete_id, run_activity)

        # Execute
        activities = data_db.get_activities_filtered(athlete_id)

        # Verify: Should return only the Run activity
        assert len(activities) == 1
        assert activities[0]["type"] == "Run"
