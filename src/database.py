import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, List, Optional


class StravaDatabase:
    def __init__(self, db_path: str = "strava_data.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Initialize the database with required tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS athletes (
                    athlete_id TEXT PRIMARY KEY,
                    first_name TEXT,
                    last_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_sync TIMESTAMP,
                    total_activities INTEGER DEFAULT 0
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS activities (
                    activity_id INTEGER PRIMARY KEY,
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
                    raw_data TEXT,  -- JSON string of full activity data
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (athlete_id) REFERENCES athletes (athlete_id)
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_athlete_activities 
                ON activities (athlete_id, start_date)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_activity_date 
                ON activities (start_date)
            """)

    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        try:
            yield conn
        finally:
            conn.close()

    def upsert_athlete(
        self, athlete_id: str, first_name: str = None, last_name: str = None
    ):
        """Insert or update athlete information."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO athletes (athlete_id, first_name, last_name, created_at, last_sync, total_activities)
                VALUES (?, ?, ?, 
                    COALESCE((SELECT created_at FROM athletes WHERE athlete_id = ?), CURRENT_TIMESTAMP),
                    CURRENT_TIMESTAMP,
                    COALESCE((SELECT total_activities FROM athletes WHERE athlete_id = ?), 0)
                )
            """,
                (athlete_id, first_name, last_name, athlete_id, athlete_id),
            )
            conn.commit()

    def get_athlete_last_sync(self, athlete_id: str) -> Optional[datetime]:
        """Get the last sync timestamp for an athlete."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT last_sync FROM athletes WHERE athlete_id = ?", (athlete_id,)
            )
            result = cursor.fetchone()
            if result and result["last_sync"]:
                return datetime.fromisoformat(result["last_sync"])
            return None

    def get_latest_activity_date(self, athlete_id: str) -> Optional[datetime]:
        """Get the date of the most recent activity for an athlete."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT start_date FROM activities 
                WHERE athlete_id = ? 
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

    def save_activities(self, athlete_id: str, activities: List[Dict]) -> int:
        """Save activities to database, avoiding duplicates."""
        saved_count = 0
        with self.get_connection() as conn:
            for activity in activities:
                # Check if activity already exists
                cursor = conn.execute(
                    "SELECT 1 FROM activities WHERE activity_id = ?", (activity["id"],)
                )
                if cursor.fetchone():
                    continue  # Skip existing activities

                # Insert new activity
                conn.execute(
                    """
                    INSERT INTO activities (
                        activity_id, athlete_id, name, type, start_date,
                        distance, moving_time, elapsed_time, total_elevation_gain,
                        average_speed, max_speed, raw_data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            conn.execute(
                """
                UPDATE athletes 
                SET total_activities = (
                    SELECT COUNT(*) FROM activities WHERE athlete_id = ?
                ), last_sync = CURRENT_TIMESTAMP
                WHERE athlete_id = ?
            """,
                (athlete_id, athlete_id),
            )

            conn.commit()

        return saved_count

    def get_activities(self, athlete_id: str, limit: int = None) -> List[Dict]:
        """Get activities for an athlete from database."""
        with self.get_connection() as conn:
            query = """
                SELECT activity_id, name, type, start_date, distance, 
                       moving_time, elapsed_time, total_elevation_gain,
                       average_speed, max_speed, raw_data
                FROM activities 
                WHERE athlete_id = ? 
                ORDER BY start_date DESC
            """
            params = [athlete_id]

            if limit:
                query += " LIMIT ?"
                params.append(limit)

            cursor = conn.execute(query, params)
            activities = []

            for row in cursor.fetchall():
                # Convert row to dict and parse raw_data if needed
                activity = dict(row)
                if activity["raw_data"]:
                    # You can merge with raw_data if you need full original data
                    pass
                activities.append(activity)

            return activities

    def get_athlete_stats(self, athlete_id: str) -> Dict:
        """Get summary stats for an athlete."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT 
                    COUNT(*) as total_activities,
                    SUM(distance) as total_distance,
                    SUM(moving_time) as total_moving_time,
                    AVG(distance) as avg_distance,
                    MIN(start_date) as first_activity,
                    MAX(start_date) as last_activity,
                    COUNT(DISTINCT type) as activity_types
                FROM activities 
                WHERE athlete_id = ?
            """,
                (athlete_id,),
            )

            result = cursor.fetchone()
            return dict(result) if result else {}

    def needs_sync(self, athlete_id: str, max_age_hours: int = 1) -> bool:
        """Check if athlete data needs syncing based on last sync time."""
        last_sync = self.get_athlete_last_sync(athlete_id)
        if not last_sync:
            return True

        age_hours = (datetime.now() - last_sync).total_seconds() / 3600
        return age_hours > max_age_hours

    def get_all_athletes(self) -> List[Dict]:
        """Get all athletes for admin/stats purposes."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT athlete_id, first_name, last_name, 
                       total_activities, last_sync, created_at
                FROM athletes 
                ORDER BY last_sync DESC
            """)
            return [dict(row) for row in cursor.fetchall()]
