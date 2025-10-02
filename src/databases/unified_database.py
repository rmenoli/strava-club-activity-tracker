from datetime import datetime
from typing import Dict, List, Optional

from .admin_database import AdminDatabase
from .strava_data_database import StravaDataDatabase


class StravaDatabase:
    """
    Unified database interface that combines AdminDatabase and StravaDataDatabase.
    This class maintains backward compatibility while delegating operations to specialized classes.
    """

    def __init__(self, db_path: str = "strava_data.db"):
        self.db_path = db_path
        self.admin_db = AdminDatabase(db_path)
        self.data_db = StravaDataDatabase(db_path)

        # Initialize both databases
        self.init_database()

    def init_database(self):
        """Initialize the database with required tables."""
        # Both classes handle their own table initialization
        self.admin_db.init_admin_tables()
        self.data_db.init_data_tables()

    # ===== ATHLETE OPERATIONS (delegate to data_db) =====

    def upsert_athlete(
        self, athlete_id: str, first_name: str = None, last_name: str = None
    ):
        """Insert or update athlete information."""
        return self.data_db.upsert_athlete(athlete_id, first_name, last_name)

    def get_athlete_last_sync(self, athlete_id: str) -> Optional[datetime]:
        """Get the last sync timestamp for an athlete."""
        return self.data_db.get_athlete_last_sync(athlete_id)

    def get_latest_activity_date(self, athlete_id: str) -> Optional[datetime]:
        """Get the date of the most recent activity for an athlete."""
        return self.data_db.get_latest_activity_date(athlete_id)

    def get_all_athletes(self) -> List[Dict]:
        """Get all athletes for admin/stats purposes."""
        return self.data_db.get_all_athletes()

    def needs_sync(self, athlete_id: str, max_age_hours: int = 1) -> bool:
        """Check if athlete data needs syncing based on last sync time."""
        return self.data_db.needs_sync(athlete_id, max_age_hours)

    def get_athlete_stats(self, athlete_id: str) -> Dict:
        """Get summary stats for an athlete."""
        return self.data_db.get_athlete_stats(athlete_id)

    # ===== ACTIVITY OPERATIONS (delegate to data_db) =====

    def save_activities(self, athlete_id: str, activities: List[Dict]) -> int:
        """Save activities to database, avoiding duplicates."""
        return self.data_db.save_activities(athlete_id, activities)

    def get_activities(self, athlete_id: str, limit: int = None) -> List[Dict]:
        """Get activities for an athlete from database."""
        return self.data_db.get_activities(athlete_id, limit)

    def filter_activities(self, activities: List[Dict]) -> List[Dict]:
        """Filter activities to include only those within radius of date-specific target locations."""
        return self.data_db.filter_activities(activities, self.admin_db)

    def get_activities_filtered(
        self, athlete_id: str, limit: int = None, activity_type: str = None
    ) -> List[Dict]:
        """Get activities with automatically extracted relevant fields from raw_data and apply GPS filtering."""
        return self.data_db.get_activities_filtered(
            athlete_id, self.admin_db, limit, activity_type
        )

    # ===== ADMIN/SETTINGS OPERATIONS (delegate to admin_db) =====

    def get_setting(self, key: str, default_value: str = None) -> Optional[str]:
        """Get a setting value by key."""
        return self.admin_db.get_setting(key, default_value)

    def set_setting(self, key: str, value: str, description: str = None) -> None:
        """Set a setting value by key."""
        return self.admin_db.set_setting(key, value, description)

    def get_all_settings(self) -> List[Dict]:
        """Get all settings for admin interface."""
        return self.admin_db.get_all_settings()

    def get_location_settings(self) -> Dict:
        """Get current location filter settings."""
        return self.admin_db.get_location_settings()

    def update_location_settings(
        self, latitude: float, longitude: float, radius_km: float = None
    ) -> None:
        """Update location filter settings."""
        return self.admin_db.update_location_settings(latitude, longitude, radius_km)

    # ===== DATE-BASED LOCATION FILTER OPERATIONS (delegate to admin_db) =====

    def add_date_location_filter(
        self,
        filter_date: str,
        latitude: float,
        longitude: float,
        radius_km: float,
        description: str = None,
    ) -> None:
        """Add or update a date-based location filter."""
        return self.admin_db.add_date_location_filter(
            filter_date, latitude, longitude, radius_km, description
        )

    def get_date_location_filter(self, filter_date: str) -> Optional[Dict]:
        """Get location filter for a specific date."""
        return self.admin_db.get_date_location_filter(filter_date)

    def get_all_date_location_filters(self) -> List[Dict]:
        """Get all date-based location filters."""
        return self.admin_db.get_all_date_location_filters()

    def delete_date_location_filter(self, filter_date: str) -> None:
        """Delete a date-based location filter."""
        return self.admin_db.delete_date_location_filter(filter_date)

    def get_location_settings_for_activity(self, activity_start_date: str) -> Dict:
        """Get location settings for a specific activity based on its date."""
        return self.admin_db.get_location_settings_for_activity(activity_start_date)

    # ===== CONTEXT MANAGERS AND UTILITIES =====

    @property
    def get_connection(self):
        """Access to connection context manager (uses data_db connection)."""
        return self.data_db.get_connection
