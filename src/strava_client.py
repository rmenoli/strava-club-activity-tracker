import time
from datetime import datetime
from typing import Dict, List, Optional

import requests


class StravaClient:
    BASE_URL = "https://www.strava.com/api/v3"
    TOKEN_URL = "https://www.strava.com/oauth/token"
    AUTH_URL = "https://www.strava.com/oauth/authorize"
    REDIRECT_URI = "http://localhost"

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.expires_at: Optional[int] = None

    def refresh_access_token(self) -> bool:
        """Refresh the access token using the refresh token."""
        if not self.refresh_token:
            print("No refresh token available")
            return False

        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
        }

        response = requests.post(self.TOKEN_URL, data=payload)

        if response.status_code == 200:
            token_data = response.json()
            self.access_token = token_data["access_token"]
            self.expires_at = token_data["expires_at"]
            self.refresh_token = token_data["refresh_token"]  # Update refresh token
            print("✓ Access token refreshed successfully")
            return True
        else:
            print(f"Failed to refresh token: {response.status_code} - {response.text}")
            return False

    def is_token_valid(self) -> bool:
        """Check if the current access token is valid and not expired."""
        if not self.access_token:
            return False

        if self.expires_at and time.time() > self.expires_at:
            return False

        return True

    def ensure_valid_token(self) -> bool:
        """Ensure we have a valid access token, refresh if needed."""
        if self.is_token_valid():
            return True

        print("Token expired or invalid, attempting to refresh...")
        return self.refresh_access_token()

    def get_activities(
        self,
        before: Optional[datetime] = None,
        after: Optional[datetime] = None,
        per_page: int = 200,
        page: int = 1,
    ) -> List[Dict]:
        """Fetch a single page of activities."""
        # Ensure we have a valid token
        if not self.ensure_valid_token():
            raise Exception("Failed to obtain valid access token")

        headers = {"Authorization": f"Bearer {self.access_token}"}
        params = {"per_page": per_page, "page": page}

        if before:
            params["before"] = int(before.timestamp())
        if after:
            params["after"] = int(after.timestamp())

        resp = requests.get(
            f"{self.BASE_URL}/athlete/activities",
            headers=headers,
            params=params,
            timeout=30,
        )

        # Handle authentication errors (401)
        if resp.status_code == 401:
            print("Token invalid, attempting to refresh...")
            if self.refresh_access_token():
                # Retry with new token
                headers = {"Authorization": f"Bearer {self.access_token}"}
                resp = requests.get(
                    f"{self.BASE_URL}/athlete/activities",
                    headers=headers,
                    params=params,
                    timeout=30,
                )
            else:
                raise Exception("Failed to refresh access token")

        # Handle rate limiting (429)
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", "15"))
            print(f"Rate limited. Sleeping {retry_after} seconds...")
            time.sleep(retry_after)
            return self.get_activities(before, after, per_page, page)

        resp.raise_for_status()
        return resp.json()

    def get_all_activities(
        self, after: Optional[datetime] = None, before: Optional[datetime] = None
    ) -> List[Dict]:
        """Get all activities with pagination."""
        all_activities = []
        page = 1

        while True:
            activities = self.get_activities(
                before=before, after=after, per_page=200, page=page
            )
            if not activities:
                break

            all_activities.extend(activities)
            print(f"Fetched page {page}: {len(activities)} activities")
            page += 1

            # Strava limit: 100 requests per 15 min → ~1 request every 9s max
            # We keep it low with 0.2s since each request fetches 200 activities
            time.sleep(0.2)

        return all_activities

    def exchange_code_for_tokens(self, code: str) -> Optional[str]:
        """Exchange authorization code for tokens (for web applications)."""
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
        }

        try:
            response = requests.post(self.TOKEN_URL, data=payload)
            response.raise_for_status()
            token_data = response.json()

            # Store tokens
            self.access_token = token_data["access_token"]
            self.refresh_token = token_data["refresh_token"]
            self.expires_at = token_data["expires_at"]

            # Get athlete ID (unique per user)
            athlete_id = token_data["athlete"]["id"]
            print(f"✓ Tokens obtained for athlete {athlete_id}")
            return str(athlete_id)  # Return as string for consistency
        except Exception as e:
            print(f"Error exchanging code for tokens: {e}")
            return None
