from datetime import datetime, timedelta
from typing import Optional

from src.database import StravaDatabase
from src.store_token import load_tokens
from src.strava_client import StravaClient


class ActivitySyncService:
    def __init__(self, db: StravaDatabase):
        self.db = db

    def should_sync(self, athlete_id: str) -> bool:
        """Determine if we should sync activities for this athlete."""
        return self.db.needs_sync(athlete_id, max_age_hours=1)

    def get_sync_start_date(self, athlete_id: str) -> Optional[datetime]:
        """Get the date from which to start syncing activities."""
        # First check when we last synced
        last_sync = self.db.get_athlete_last_sync(athlete_id)

        # Then check the latest activity date
        latest_activity = self.db.get_latest_activity_date(athlete_id)

        if latest_activity:
            # Start from latest activity date to catch any updates
            return latest_activity - timedelta(days=1)  # Small overlap to catch updates
        elif last_sync:
            # If no activities but we synced before, go back a week
            return last_sync - timedelta(days=7)
        else:
            # First time sync - go back to start of year or reasonable period
            return datetime(2025, 1, 1)

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
        """Sync activities using stored tokens."""
        # Load stored tokens
        tokens = load_tokens()
        if athlete_id not in tokens:
            return {
                "athlete_id": athlete_id,
                "synced": False,
                "error": "No stored tokens found for athlete",
            }

        # Create client with environment variables
        import os

        from dotenv import load_dotenv

        load_dotenv()
        client_id = os.getenv("STRAVA_CLIENT_ID")
        client_secret = os.getenv("STRAVA_CLIENT_SECRET")

        if not client_id or not client_secret:
            return {
                "synced": False,
                "error": "Strava client credentials not configured",
            }

        client = StravaClient(client_id, client_secret)

        # Load the stored tokens
        token_data = tokens[athlete_id]
        client.access_token = token_data["access_token"]
        client.refresh_token = token_data["refresh_token"]
        client.expires_at = token_data["expires_at"]

        return self.sync_athlete_activities(athlete_id, client)

    def background_sync_all_athletes(self) -> list:
        """Background job to sync all athletes with stored tokens."""
        results = []
        athletes = self.db.get_all_athletes()

        for athlete in athletes:
            athlete_id = athlete["athlete_id"]
            if self.should_sync(athlete_id):
                result = self.sync_athlete_with_stored_tokens(athlete_id)
                results.append(result)
            else:
                results.append(
                    {
                        "athlete_id": athlete_id,
                        "synced": False,
                        "message": "Sync not needed",
                    }
                )

        return results

    def get_athlete_summary(self, athlete_id: str) -> dict:
        """Get a summary of athlete's activities and sync status."""
        stats = self.db.get_athlete_stats(athlete_id)
        last_sync = self.db.get_athlete_last_sync(athlete_id)
        needs_sync = self.should_sync(athlete_id)

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
