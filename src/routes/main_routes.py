"""
Non-admin routes: login, index, callback, logout, sync_activities, download_csv, stats
"""

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.config import Config
from src.databases.admin_database import AdminDatabase
from src.databases.strava_data_database import StravaDataDatabase
from src.strava_client import StravaClient
from src.sync_service import ActivitySyncService

templates = Jinja2Templates(directory="templates")


def setup_main_routes(
    app: FastAPI,
    data_db: StravaDataDatabase,
    admin_db: AdminDatabase,
    sync_service: ActivitySyncService,
    config: Config,
) -> None:
    """Setup main application routes (non-admin)"""

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        athlete_id = request.session.get("athlete_id")

        if athlete_id:
            try:
                # Get activities from database with location filtering
                activities = data_db.get_activities_filtered(
                    athlete_id, admin_db, limit=100
                )  # Limit for performance

                if activities:
                    # Get athlete summary stats (filtered by location)
                    summary = data_db.get_athlete_summary(athlete_id, admin_db)

                    # Get the activity filter days setting
                    activity_filter_days = admin_db.get_activity_filter_days()

                    # Get the discount threshold setting
                    discount_threshold = admin_db.get_discount_threshold()

                    return templates.TemplateResponse(
                        "dashboard.html",
                        {
                            "request": request,
                            "athlete_id": athlete_id,
                            "activities": activities,
                            "summary": summary,
                            "activity_filter_days": activity_filter_days,
                            "discount_threshold": discount_threshold,
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
        auth_url = (
            f"https://www.strava.com/oauth/authorize?"
            f"client_id={config.STRAVA_CLIENT_ID}&response_type=code&"
            f"redirect_uri={config.STRAVA_REDIRECT_URI}&scope=activity:read_all"
        )
        return RedirectResponse(auth_url)

    @app.get("/auth/strava/callback")
    async def callback(request: Request, code: str):
        client = StravaClient(config.STRAVA_CLIENT_ID, config.STRAVA_CLIENT_SECRET)
        athlete_id = client.exchange_code_for_tokens(code)

        if not athlete_id:
            return HTMLResponse(
                "<h3>Error: Failed to get athlete ID. Please try again.</h3>"
            )

        # Store session
        request.session["athlete_id"] = athlete_id

        # Register athlete in database (upsert)
        data_db.upsert_athlete(athlete_id)

        # Save OAuth tokens to database
        data_db.save_athlete_tokens(
            athlete_id, client.access_token, client.refresh_token, client.expires_at
        )

        # Smart sync: only sync if needed
        try:
            sync_service.sync_athlete_activities(athlete_id, client)
        except Exception:
            # Don't fail the login if sync fails
            pass

        return RedirectResponse("/")

    @app.get("/logout")
    async def logout(request: Request):
        request.session.clear()
        return RedirectResponse("/")

    @app.get("/discounts")
    async def discounts(request: Request):
        """Discounts and rewards page for active athletes."""
        athlete_id = request.session.get("athlete_id")
        if not athlete_id:
            return RedirectResponse("/login")

        # Get athlete summary to show stats on discounts page
        summary = data_db.get_athlete_summary(athlete_id, admin_db)

        return templates.TemplateResponse(
            "discount.html",
            {
                "request": request,
                "athlete_id": athlete_id,
                "summary": summary,
            },
        )

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
