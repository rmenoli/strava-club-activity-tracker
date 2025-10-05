import json
import math
import psycopg2
from contextlib import contextmanager
from datetime import datetime
from psycopg2.extras import RealDictCursor
from typing import Dict, List, Optional

from src.databases.admin_database import AdminDatabase


class StravaDataDatabase:
    """Database operations for core Strava data: athletes, activities, and GPS filtering."""

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.init_data_tables()

    def init_data_tables(self):
        """Initialize core data database tables."""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS athletes (
                        athlete_id TEXT PRIMARY KEY,
                        first_name TEXT,
                        last_name TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_sync TIMESTAMP,
                        total_activities INTEGER DEFAULT 0
                    )
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS activities (
                        activity_id BIGINT PRIMARY KEY,
                        athlete_id TEXT,
                        name TEXT,
                        type TEXT,
                        start_date TEXT,
                        distance REAL,
                        moving_time INTEGER,
                        elapsed_time INTEGER,
                        total_elevation_gain REAL,
                        average_speed REAL,
                        max_speed REAL,
                        raw_data TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (athlete_id) REFERENCES athletes (athlete_id)
                    )
                """)

                # Indexes for performance
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_athlete_activities
                    ON activities (athlete_id, start_date)
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_activity_date
                    ON activities (start_date)
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

    # ===== GPS UTILITIES =====

    def calculate_distance(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """
        Calculate the great-circle distance between two points on Earth using the Haversine formula.

        Args:
            lat1, lon1: Latitude and longitude of first point in degrees
            lat2, lon2: Latitude and longitude of second point in degrees

        Returns:
            Distance in kilometers
        """
        # Convert degrees to radians
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        lon1_rad = math.radians(lon1)
        lon2_rad = math.radians(lon2)

        # Haversine formula
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))

        # Earth's radius in kilometers
        earth_radius_km = 6371.0

        return earth_radius_km * c

    # ===== ATHLETE MANAGEMENT =====

    def upsert_athlete(
        self, athlete_id: str, first_name: str = None, last_name: str = None
    ):
        """Insert or update athlete information."""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO athletes (athlete_id, first_name, last_name, last_sync, total_activities)
                    VALUES (%s, %s, %s, CURRENT_TIMESTAMP, 0)
                    ON CONFLICT (athlete_id) DO UPDATE SET
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name,
                        last_sync = CURRENT_TIMESTAMP
                """,
                    (athlete_id, first_name, last_name),
                )
                conn.commit()

    def get_athlete_last_sync(self, athlete_id: str) -> Optional[datetime]:
        """Get the last sync timestamp for an athlete."""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    "SELECT last_sync FROM athletes WHERE athlete_id = %s", (athlete_id,)
                )
                result = cursor.fetchone()
                if result and result["last_sync"]:
                    return datetime.fromisoformat(str(result["last_sync"]))
                return None

    def get_latest_activity_date(self, athlete_id: str) -> Optional[datetime]:
        """Get the date of the most recent activity for an athlete."""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT start_date FROM activities
                    WHERE athlete_id = %s
                    ORDER BY start_date DESC
                    LIMIT 1
                """,
                    (athlete_id,),
                )
                result = cursor.fetchone()
                if result:
                    return datetime.fromisoformat(
                        result["start_date"].replace("Z", "+00:00")
                    )
                return None

    def get_all_athletes(self) -> List[Dict]:
        """Get all athletes for admin/stats purposes."""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT athlete_id, first_name, last_name,
                           total_activities, last_sync, created_at
                    FROM athletes
                    ORDER BY last_sync DESC
                """)
                return [dict(row) for row in cursor.fetchall()]

    def needs_sync(self, athlete_id: str, max_age_hours: int = 1) -> bool:
        """Check if athlete data needs syncing based on last sync time."""
        last_sync = self.get_athlete_last_sync(athlete_id)
        if not last_sync:
            return True

        age_hours = (datetime.now() - last_sync).total_seconds() / 3600
        return age_hours > max_age_hours

    def get_athlete_stats(
        self, athlete_id: str, admin_db: AdminDatabase = None
    ) -> Dict:
        """
        Get summary stats for an athlete.

        If admin_db is provided, only counts activities that match location filters.
        """
        if not admin_db:
            # No filtering - use simple SQL query
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(
                        """
                        SELECT
                            COUNT(*) as total_activities,
                            SUM(distance) as total_distance,
                            SUM(moving_time) as total_moving_time
                        FROM activities
                        WHERE athlete_id = %s
                    """,
                        (athlete_id,),
                    )
                    result = cursor.fetchone()
                    return dict(result) if result else {}

        # With location filtering - get all activities and filter in Python
        activities = self.get_activities_filtered(athlete_id, admin_db)

        # Filter to only matching activities
        matching_activities = [
            a for a in activities if a.get("matches_location_filter", False)
        ]

        # Calculate stats
        total_activities = len(matching_activities)
        total_distance = sum(a.get("distance", 0) for a in matching_activities)
        total_moving_time = sum(a.get("moving_time", 0) for a in matching_activities)

        return {
            "total_activities": total_activities,
            "total_distance": total_distance,
            "total_moving_time": total_moving_time,
        }

    def get_athlete_summary(
        self, athlete_id: str, admin_db: AdminDatabase = None
    ) -> dict:
        """
        Get a summary of athlete's activities and sync status.

        If admin_db is provided, stats will only include activities matching location filters.
        """
        stats = self.get_athlete_stats(athlete_id, admin_db)
        last_sync = self.get_athlete_last_sync(athlete_id)
        needs_sync = self.needs_sync(athlete_id)

        return {
            "athlete_id": athlete_id,
            "stats": stats,
            "last_sync": last_sync.isoformat() if last_sync else None,
            "needs_sync": needs_sync,
            "sync_age_hours": (
                (datetime.now() - last_sync).total_seconds() / 3600
                if last_sync
                else None
            ),
        }

    # ===== ACTIVITY MANAGEMENT =====

    def save_activities(self, athlete_id: str, activities: List[Dict]) -> int:
        """Save activities to database, avoiding duplicates."""
        saved_count = 0
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                for activity in activities:
                    # Check if activity already exists
                    cursor.execute(
                        "SELECT 1 FROM activities WHERE activity_id = %s", (activity["id"],)
                    )
                    if cursor.fetchone():
                        continue  # Skip existing activities

                    # Insert new activity
                    cursor.execute(
                        """
                        INSERT INTO activities (
                            activity_id, athlete_id, name, type, start_date,
                            distance, moving_time, elapsed_time, total_elevation_gain,
                            average_speed, max_speed, raw_data
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                        (
                            activity["id"],
                            athlete_id,
                            activity.get("name", ""),
                            activity.get("type", ""),
                            activity.get("start_date", ""),
                            activity.get("distance", 0),
                            activity.get("moving_time", 0),
                            activity.get("elapsed_time", 0),
                            activity.get("total_elevation_gain", 0),
                            activity.get("average_speed", 0),
                            activity.get("max_speed", 0),
                            json.dumps(activity),  # Store full data as JSON
                        ),
                    )
                    saved_count += 1

                # Update athlete's total activity count and last sync
                cursor.execute(
                    """
                    UPDATE athletes
                    SET total_activities = (
                        SELECT COUNT(*) FROM activities WHERE athlete_id = %s
                    ), last_sync = CURRENT_TIMESTAMP
                    WHERE athlete_id = %s
                """,
                    (athlete_id, athlete_id),
                )

                conn.commit()

        return saved_count

    def get_activities(self, athlete_id: str, limit: int = None) -> List[Dict]:
        """Get activities for an athlete from database."""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                query = """
                    SELECT activity_id, name, type, start_date, distance,
                           moving_time, elapsed_time, total_elevation_gain,
                           average_speed, max_speed, raw_data
                    FROM activities
                    WHERE athlete_id = %s
                    ORDER BY start_date DESC
                """
                params = [athlete_id]

                if limit:
                    query += " LIMIT %s"
                    params.append(limit)

                cursor.execute(query, params)
                activities = []

                for row in cursor.fetchall():
                    activity = dict(row)
                    activities.append(activity)

                return activities

    # ===== ACTIVITY FILTERING =====

    def _apply_location_filter(
        self, activity: Dict, raw_data: Dict, admin_db: AdminDatabase
    ) -> None:
        """
        Apply location filtering to an activity and add filter match information.

        Modifies the activity dict in-place to add:
        - matches_location_filter: Boolean
        - filter_info: Dict with location, radius, and source information

        Args:
            activity: Activity dict to modify
            raw_data: Raw Strava API response data
            admin_db: AdminDatabase instance for getting location settings
        """
        # Initialize filter info
        activity["matches_location_filter"] = False
        activity["filter_info"] = None

        # Get GPS coordinates
        start_latlng = raw_data.get("start_latlng")
        end_latlng = raw_data.get("end_latlng")

        # Skip if no GPS data
        if not start_latlng or not end_latlng:
            return

        # Skip if coordinates are incomplete
        if len(start_latlng) != 2 or len(end_latlng) != 2:
            return

        # Get location settings for this activity's date
        location_settings = admin_db.get_location_settings_for_activity(
            activity["start_date"]
        )

        target_lat = location_settings["target_latitude"]
        target_lon = location_settings["target_longitude"]
        radius_km = location_settings["filter_radius_km"]
        filter_source = location_settings["source"]

        # Calculate distances
        start_distance = self.calculate_distance(
            start_latlng[0], start_latlng[1], target_lat, target_lon
        )
        end_distance = self.calculate_distance(
            end_latlng[0], end_latlng[1], target_lat, target_lon
        )

        # Check if BOTH start and end are within radius
        matches = start_distance <= radius_km and end_distance <= radius_km

        # Add filter information to activity
        activity["matches_location_filter"] = matches
        activity["filter_info"] = {
            "target_location": [target_lat, target_lon],
            "radius_km": radius_km,
            "source": filter_source,  # 'default' or 'date_specific'
            "start_distance_km": round(start_distance, 2),
            "end_distance_km": round(end_distance, 2),
        }

        # Add filter date if date-specific
        if "filter_date" in location_settings:
            activity["filter_info"]["filter_date"] = location_settings["filter_date"]

    def get_activities_filtered(
        self,
        athlete_id: str,
        admin_db: AdminDatabase = None,
        limit: int = None,
        activity_type: str = None,
    ) -> List[Dict]:
        """
        Get activities with automatically extracted relevant fields from raw_data.

        If admin_db is provided, adds location filter matching information:
        - matches_location_filter: Boolean indicating if activity matches date-location filter
        - filter_info: Details about the filter used (location, radius, source)
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                query = """
                    SELECT activity_id, athlete_id, name, type, start_date, distance,
                           moving_time, elapsed_time, total_elevation_gain,
                           average_speed, max_speed, raw_data
                    FROM activities
                    WHERE athlete_id = %s
                """
                params = [athlete_id]

                # Add activity type filter if specified
                if activity_type:
                    query += " AND type = %s"
                    params.append(activity_type)

                query += " ORDER BY start_date DESC"

                if limit:
                    query += " LIMIT %s"
                    params.append(limit)

                cursor.execute(query, params)
                activities = []

                for row in cursor.fetchall():
                    activity = dict(row)

                    # Start with basic activity data
                    filtered_activity = {
                        "activity_id": activity["activity_id"],
                        "athlete_id": activity["athlete_id"],
                        "name": activity["name"],
                        "type": activity["type"],
                        "start_date": activity["start_date"],
                        "distance": activity["distance"],
                        "moving_time": activity["moving_time"],
                    }

                    # Parse and extract relevant fields from raw_data
                    if activity["raw_data"]:
                        try:
                            raw_data = json.loads(activity["raw_data"])

                            # Extract specific fields from raw_data
                            extracted_fields = {
                                "start_latlng": raw_data.get("start_latlng"),
                                "end_latlng": raw_data.get("end_latlng"),
                                "athlete_count": raw_data.get("athlete_count"),
                                "photo_count": raw_data.get("photo_count"),
                                "kudos_count": raw_data.get("kudos_count"),
                                "comment_count": raw_data.get("comment_count"),
                                "has_kudos": raw_data.get("has_kudos"),
                                "pr_count": raw_data.get("pr_count"),
                            }

                            # Add extracted fields to activity
                            filtered_activity.update(extracted_fields)

                            # Apply location filtering if admin_db is provided
                            if admin_db:
                                self._apply_location_filter(
                                    filtered_activity, raw_data, admin_db
                                )

                        except (json.JSONDecodeError, TypeError) as e:
                            # If JSON parsing fails, continue without extracted fields
                            print(
                                f"Warning: Could not parse raw_data for activity {activity['activity_id']}: {e}"
                            )

                activities.append(filtered_activity)

            return activities
