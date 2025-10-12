import psycopg2
from contextlib import contextmanager
from psycopg2.extras import RealDictCursor
from typing import Dict, List, Optional


class AdminDatabase:
    """Database operations for admin settings, configurations, and date-based location filters."""

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.init_admin_tables()

    def init_admin_tables(self):
        """Initialize admin-related database tables."""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                # Settings table for configurable parameters
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY,
                        value TEXT,
                        description TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Insert default location settings if they don't exist
                cursor.execute("""
                    INSERT INTO settings (key, value, description)
                    VALUES
                        ('target_latitude', '50.097416', 'Default target location latitude for activity filtering'),
                        ('target_longitude', '14.462274', 'Default target location longitude for activity filtering'),
                        ('filter_radius_km', '1.0', 'Default radius in kilometers for location filtering'),
                        ('activity_filter_days', '90', 'Number of days of activity history to include in statistics'),
                        ('discount_threshold_activities', '5', 'Minimum number of activities required to access discount features')
                    ON CONFLICT (key) DO NOTHING
                """)

                # Date-based location filters table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS date_location_filters (
                        id SERIAL PRIMARY KEY,
                        filter_date DATE NOT NULL,
                        target_latitude REAL NOT NULL,
                        target_longitude REAL NOT NULL,
                        radius_km REAL NOT NULL DEFAULT 1.0,
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(filter_date)
                    )
                """)

                # Index for date-based lookups
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_date_filters_date
                    ON date_location_filters (filter_date)
                """)

                conn.commit()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = psycopg2.connect(self.db_url)
        try:
            yield conn
        finally:
            conn.close()

    # ===== SETTINGS MANAGEMENT =====

    def get_setting(self, key: str, default_value: str = None) -> Optional[str]:
        """Get a setting value by key."""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SELECT value FROM settings WHERE key = %s", (key,))
                result = cursor.fetchone()
                return result["value"] if result else default_value

    # ===== LOCATION SETTINGS =====

    def get_location_settings(self) -> Dict:
        """Get current location filter settings."""
        return {
            "target_latitude": float(self.get_setting("target_latitude", "50.097416")),
            "target_longitude": float(
                self.get_setting("target_longitude", "14.462274")
            ),
            "filter_radius_km": float(self.get_setting("filter_radius_km", "1.0")),
        }

    def get_activity_filter_days(self) -> int:
        """Get the number of days of activity history to include in statistics."""
        return int(self.get_setting("activity_filter_days", "90"))

    def update_activity_filter_days(self, days: int) -> None:
        """Update the number of days of activity history to include in statistics."""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO settings (key, value, updated_at)
                    VALUES ('activity_filter_days', %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (key) DO UPDATE SET
                        value = EXCLUDED.value,
                        updated_at = CURRENT_TIMESTAMP
                """,
                    (str(days),),
                )
                conn.commit()

    def get_discount_threshold(self) -> int:
        """Get the minimum number of activities required to access discount features."""
        return int(self.get_setting("discount_threshold_activities", "5"))

    def update_discount_threshold(self, threshold: int) -> None:
        """Update the minimum number of activities required to access discount features."""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO settings (key, value, updated_at)
                    VALUES ('discount_threshold_activities', %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (key) DO UPDATE SET
                        value = EXCLUDED.value,
                        updated_at = CURRENT_TIMESTAMP
                """,
                    (str(threshold),),
                )
                conn.commit()

    # ===== DATE-BASED LOCATION FILTERS =====

    def add_date_location_filter(
        self,
        filter_date: str,
        latitude: float,
        longitude: float,
        radius_km: float,
        description: str = None,
    ) -> None:
        """Add or update a date-based location filter."""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO date_location_filters
                    (filter_date, target_latitude, target_longitude, radius_km, description, updated_at)
                    VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (filter_date) DO UPDATE SET
                        target_latitude = EXCLUDED.target_latitude,
                        target_longitude = EXCLUDED.target_longitude,
                        radius_km = EXCLUDED.radius_km,
                        description = EXCLUDED.description,
                        updated_at = CURRENT_TIMESTAMP
                """,
                    (filter_date, latitude, longitude, radius_km, description),
                )
                conn.commit()

    def get_date_location_filter(self, filter_date: str) -> Optional[Dict]:
        """Get location filter for a specific date."""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT filter_date, target_latitude, target_longitude, radius_km, description
                    FROM date_location_filters
                    WHERE filter_date = %s
                """,
                    (filter_date,),
                )
                result = cursor.fetchone()
                return dict(result) if result else None

    def get_all_date_location_filters(self) -> List[Dict]:
        """Get all date-based location filters."""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT filter_date, target_latitude, target_longitude, radius_km, description, created_at, updated_at
                    FROM date_location_filters
                    ORDER BY filter_date DESC
                """)
                return [dict(row) for row in cursor.fetchall()]

    def delete_date_location_filter(self, filter_date: str) -> None:
        """Delete a date-based location filter."""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM date_location_filters WHERE filter_date = %s",
                    (filter_date,),
                )
                conn.commit()

    def get_location_settings_for_activity(self, activity_start_date: str) -> Dict:
        """Get location settings for a specific activity based on its date."""
        # Extract date from activity start_date (format: 2024-10-02T07:30:00Z)
        activity_date = activity_start_date[:10]  # Get YYYY-MM-DD part

        # Check if there's a specific filter for this date
        date_filter = self.get_date_location_filter(activity_date)

        if date_filter:
            return {
                "target_latitude": date_filter["target_latitude"],
                "target_longitude": date_filter["target_longitude"],
                "filter_radius_km": date_filter["radius_km"],
                "source": "date_specific",
                "filter_date": activity_date,
            }
        else:
            # Fall back to default settings
            default_settings = self.get_location_settings()
            default_settings["source"] = "default"
            default_settings["filter_date"] = None
            return default_settings
