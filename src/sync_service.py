from datetime import datetime, timedelta
from typing import Optional

from src.config import Config
from src.databases.strava_data_database import StravaDataDatabase
from src.strava_client import StravaClient


class ActivitySyncService:
    def __init__(self, db: StravaDataDatabase, config: Config):
        """Initialize with a database instance and configuration.

        Args:
            db: Database instance (AdminDatabase or StravaDataDatabase)
            config: Application configuration instance
        """
        self.db = db
        self.config = config

    def should_sync(self, athlete_id: str) -> bool:
        """Determine if we should sync activities for this athlete."""
        return self.db.needs_sync(athlete_id, max_age_hours=1)

    def get_sync_start_date(self, athlete_id: str) -> Optional[datetime]:
        """Get the date from which to start syncing activities."""
        # Check the latest activity date
        latest_activity = self.db.get_latest_activity_date(athlete_id)

        if latest_activity:
            # Start from latest activity date to catch any updates
            return latest_activity - timedelta(days=1)  # Small overlap to catch updates
        else:
            # First time sync - go back six months from now
            return datetime.now() - timedelta(days=180)

    def sync_athlete_activities(self, athlete_id: str, client: StravaClient) -> dict:
        """Sync activities for a specific athlete."""
        result = {
            "athlete_id": athlete_id,
            "synced": False,
            "new_activities": 0,
            "total_activities": 0,
            "error": None,
        }

        try:
            # Check if sync is needed
            if not self.should_sync(athlete_id):
                existing_count = len(self.db.get_activities(athlete_id, limit=1))
                result.update(
                    {
                        "synced": False,
                        "new_activities": 0,
                        "total_activities": existing_count,
                        "message": "Sync not needed - data is fresh",
                    }
                )
                return result

            # Get the appropriate start date for syncing
            sync_from_date = self.get_sync_start_date(athlete_id)
            print(f"Syncing activities for athlete {athlete_id} from {sync_from_date}")

            # Fetch activities from Strava
            activities = client.get_all_activities(after=sync_from_date)

            # Save to database
            new_count = self.db.save_activities(athlete_id, activities)
            total_count = len(self.db.get_activities(athlete_id))

            # Save potentially refreshed tokens back to database
            self.db.save_athlete_tokens(
                athlete_id, client.access_token, client.refresh_token, client.expires_at
            )

            result.update(
                {
                    "synced": True,
                    "new_activities": new_count,
                    "total_activities": total_count,
                    "sync_from_date": sync_from_date.isoformat(),
                    "message": f"Successfully synced {new_count} new activities",
                }
            )

            print(f"Sync complete for athlete {athlete_id}: {new_count} new activities")

        except Exception as e:
            result["error"] = str(e)
            print(f"Sync failed for athlete {athlete_id}: {e}")

        return result

    def sync_athlete_with_stored_tokens(self, athlete_id: str) -> dict:
        """Sync activities using stored tokens from database."""
        # Load stored tokens from database
        token_data = self.db.get_athlete_tokens(athlete_id)
        if not token_data:
            return {
                "athlete_id": athlete_id,
                "synced": False,
                "error": "No stored tokens found for athlete",
            }

        # Create client with credentials from config
        client = StravaClient(
            self.config.STRAVA_CLIENT_ID, self.config.STRAVA_CLIENT_SECRET
        )

        # Load the stored tokens
        client.access_token = token_data["access_token"]
        client.refresh_token = token_data["refresh_token"]
        client.expires_at = token_data["expires_at"]

        return self.sync_athlete_activities(athlete_id, client)
