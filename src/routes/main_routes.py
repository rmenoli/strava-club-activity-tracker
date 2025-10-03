"""
Non-admin routes: login, index, callback, logout, sync_activities, download_csv, stats
"""

import os

from fastapi import Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.store_token import load_tokens, save_tokens
from src.strava_client import StravaClient

templates = Jinja2Templates(directory="templates")


def setup_main_routes(app, data_db, admin_db, sync_service):
    """Setup main application routes (non-admin)"""

    client_id = os.getenv("STRAVA_CLIENT_ID")
    client_secret = os.getenv("STRAVA_CLIENT_SECRET")

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        # Debug session contents
        print(f"Full session data: {dict(request.session)}")
        athlete_id = request.session.get("athlete_id")

        # Debug logging (remove in production)
        print(f"Athlete ID from session: {athlete_id}")

        if athlete_id:
            try:
                # Get activities from database with location filtering
                activities = data_db.get_activities_filtered(
                    athlete_id, admin_db, limit=100, activity_type="Run"
                )  # Limit for performance

                if activities:
                    # Get athlete summary stats
                    summary = sync_service.get_athlete_summary(athlete_id)

                    return templates.TemplateResponse(
                        "dashboard.html",
                        {
                            "request": request,
                            "athlete_id": athlete_id,
                            "activities": activities,
                            "summary": summary,
                        },
                    )
                else:
                    return HTMLResponse(
                        "<h3>No activities found. <a href='/sync'>Sync your activities</a> or <a href='/login'>Login again</a></h3>"
                    )
            except Exception as e:
                print(f"Error loading activities from database: {e}")
                return HTMLResponse(
                    "<h3>Error loading activities. Please try logging in again.</h3>"
                )

        # User is not logged in - show login page
        return templates.TemplateResponse("index.html", {"request": request})

    @app.get("/login")
    async def login():
        redirect_uri = os.getenv("REDIRECT_URI", "http://localhost:8000/callback")
        auth_url = (
            f"https://www.strava.com/oauth/authorize?"
            f"client_id={client_id}&response_type=code&"
            f"redirect_uri={redirect_uri}&scope=activity:read_all"
        )
        return RedirectResponse(auth_url)

    @app.get("/callback")
    async def callback(request: Request, code: str):
        print(f"Callback received with code: {code[:10]}...")

        client = StravaClient(client_id, client_secret)
        athlete_id = client.exchange_code_for_tokens(code)

        print(f"Got athlete_id: {athlete_id}")

        if not athlete_id:
            print("ERROR: No athlete_id received from token exchange!")
            return HTMLResponse(
                "<h3>Error: Failed to get athlete ID. Please try again.</h3>"
            )

        tokens = load_tokens()
        tokens[athlete_id] = {
            "access_token": client.access_token,
            "refresh_token": client.refresh_token,
            "expires_at": client.expires_at,
        }
        save_tokens(tokens)

        # store session
        request.session["athlete_id"] = athlete_id
        print(f"Session set with athlete_id: {request.session.get('athlete_id')}")

        # Register athlete in database (upsert)
        data_db.upsert_athlete(athlete_id)

        # Smart sync: only sync if needed
        try:
            sync_result = sync_service.sync_athlete_activities(athlete_id, client)
            print(f"Sync result: {sync_result}")
        except Exception as e:
            print(f"Error during sync: {e}")
            # Don't fail the login if sync fails

        return RedirectResponse("/")

    @app.get("/logout")
    async def logout(request: Request):
        request.session.clear()
        return RedirectResponse("/")

    @app.get("/test-session")
    async def test_session(request: Request):
        # Test if sessions work at all
        count = request.session.get("test_count", 0)
        count += 1
        request.session["test_count"] = count
        return {"message": f"Session test count: {count}"}

    @app.get("/sync")
    async def sync_activities(request: Request):
        """Manually trigger sync for the logged-in athlete."""
        athlete_id = request.session.get("athlete_id")
        if not athlete_id:
            return RedirectResponse("/login")

        try:
            sync_result = sync_service.sync_athlete_with_stored_tokens(athlete_id)
            if sync_result["synced"]:
                message = f"✅ Synced {sync_result['new_activities']} new activities"
            else:
                message = f"ℹ️ {sync_result.get('message', 'No sync needed')}"
        except Exception as e:
            message = f"❌ Sync failed: {str(e)}"

        return HTMLResponse(
            f"<h3>{message}</h3><p><a href='/'>Back to Dashboard</a></p>"
        )

    @app.get("/download")
    async def download_csv(request: Request):
        """Export activities as CSV for the logged-in athlete."""
        athlete_id = request.session.get("athlete_id")
        if not athlete_id:
            return RedirectResponse("/login")

        # Get activities from database
        activities = data_db.get_activities(athlete_id)

        if not activities:
            return HTMLResponse("<h3>No activities to download</h3>")

        # Convert to pandas and save as CSV temporarily
        import pandas as pd

        df = pd.DataFrame(activities)
        filename = f"activities_{athlete_id}.csv"
        df.to_csv(filename, index=False)

        return FileResponse(filename, filename=f"activities_{athlete_id}.csv")
