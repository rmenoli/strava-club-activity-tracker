import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from src.admin_database import AdminDatabase
from src.store_token import load_tokens, save_tokens
from src.strava_client import StravaClient
from src.strava_data_database import StravaDataDatabase
from src.sync_service import ActivitySyncService

load_dotenv()

# Initialize database and sync service
admin_db = AdminDatabase()
data_db = StravaDataDatabase()
sync_service = ActivitySyncService(data_db)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Session middleware (cookie-based session storage)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "dev-secret"),
)

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
            # Get activities from database
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

    return HTMLResponse(f"<h3>{message}</h3><p><a href='/'>Back to Dashboard</a></p>")


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


@app.get("/stats")
async def athlete_stats(request: Request):
    """Show detailed stats for the logged-in athlete."""
    athlete_id = request.session.get("athlete_id")
    if not athlete_id:
        return RedirectResponse("/login")

    summary = sync_service.get_athlete_summary(athlete_id)
    stats = summary["stats"]

    return templates.TemplateResponse(
        "stats.html",
        {
            "request": request,
            "athlete_id": athlete_id,
            "summary": summary,
            "stats": stats,
        },
    )


@app.get("/admin")
async def admin_dashboard(request: Request):
    """Admin dashboard showing all athletes (for development)."""
    from datetime import datetime

    athletes = data_db.get_all_athletes()

    # Add sync status calculation for each athlete
    for athlete in athletes:
        if athlete.get("last_sync"):
            try:
                # Parse the sync date and calculate hours ago
                sync_dt = datetime.fromisoformat(
                    athlete["last_sync"].replace("Z", "+00:00")
                )
                hours_ago = (
                    datetime.now() - sync_dt.replace(tzinfo=None)
                ).total_seconds() / 3600

                if hours_ago < 24:
                    athlete["sync_status"] = "recent"
                elif hours_ago < 168:  # 1 week
                    athlete["sync_status"] = "old"
                else:
                    athlete["sync_status"] = "very_old"
            except (ValueError, TypeError):
                athlete["sync_status"] = "unknown"
        else:
            athlete["sync_status"] = "never"

    return templates.TemplateResponse(
        "admin.html", {"request": request, "athletes": athletes}
    )


@app.get("/admin/settings")
async def admin_settings(request: Request):
    """Admin settings page for configuring location filters."""
    settings = admin_db.get_all_settings()
    location_settings = admin_db.get_location_settings()

    return templates.TemplateResponse(
        "admin_settings.html",
        {"request": request, "settings": settings, "location": location_settings},
    )


@app.post("/admin/settings/location")
async def update_location_settings(request: Request):
    """Update location filter settings."""
    form_data = await request.form()

    try:
        latitude = float(form_data.get("latitude"))
        longitude = float(form_data.get("longitude"))
        radius_km = float(form_data.get("radius_km", 1.0))

        # Validate latitude and longitude ranges
        if not (-90 <= latitude <= 90):
            raise ValueError("Latitude must be between -90 and 90")
        if not (-180 <= longitude <= 180):
            raise ValueError("Longitude must be between -180 and 180")
        if not (0.1 <= radius_km <= 50):
            raise ValueError("Radius must be between 0.1 and 50 km")

        admin_db.update_location_settings(latitude, longitude, radius_km)

        return HTMLResponse(f"""
            <h3>✅ Location settings updated successfully!</h3>
            <p>New target location: [{latitude}, {longitude}]</p>
            <p>Filter radius: {radius_km} km</p>
            <p><a href='/admin/settings'>Back to Settings</a> | <a href='/admin'>Admin Dashboard</a></p>
        """)

    except (ValueError, TypeError) as e:
        return HTMLResponse(f"""
            <h3>❌ Error updating location settings</h3>
            <p>Error: {str(e)}</p>
            <p><a href='/admin/settings'>Back to Settings</a></p>
        """)


@app.get("/api/location-settings")
async def get_location_settings():
    """API endpoint to get current location settings."""
    return admin_db.get_location_settings()


@app.get("/admin/date-filters")
async def admin_date_filters(request: Request):
    """Admin page for managing date-based location filters."""
    date_filters = admin_db.get_all_date_location_filters()
    default_location = admin_db.get_location_settings()

    return templates.TemplateResponse(
        "admin_date_filters.html",
        {
            "request": request,
            "date_filters": date_filters,
            "default_location": default_location,
        },
    )


@app.post("/admin/date-filters/add")
async def add_date_filter(request: Request):
    """Add a new date-based location filter."""
    form_data = await request.form()

    try:
        filter_date = form_data.get("filter_date")
        latitude = float(form_data.get("latitude"))
        longitude = float(form_data.get("longitude"))
        radius_km = float(form_data.get("radius_km", 1.0))
        description = form_data.get("description", "").strip()

        # Validate inputs
        if not filter_date:
            raise ValueError("Date is required")
        if not (-90 <= latitude <= 90):
            raise ValueError("Latitude must be between -90 and 90")
        if not (-180 <= longitude <= 180):
            raise ValueError("Longitude must be between -180 and 180")
        if not (0.1 <= radius_km <= 50):
            raise ValueError("Radius must be between 0.1 and 50 km")

        admin_db.add_date_location_filter(
            filter_date, latitude, longitude, radius_km, description
        )

        return HTMLResponse(f"""
            <h3>✅ Date filter added successfully!</h3>
            <p>Date: {filter_date}</p>
            <p>Location: [{latitude}, {longitude}]</p>
            <p>Radius: {radius_km} km</p>
            <p>Description: {description or "No description"}</p>
            <p><a href='/admin/date-filters'>Back to Date Filters</a> | <a href='/admin'>Admin Dashboard</a></p>
        """)

    except (ValueError, TypeError) as e:
        return HTMLResponse(f"""
            <h3>❌ Error adding date filter</h3>
            <p>Error: {str(e)}</p>
            <p><a href='/admin/date-filters'>Back to Date Filters</a></p>
        """)


@app.post("/admin/date-filters/delete/{filter_date}")
async def delete_date_filter(filter_date: str):
    """Delete a date-based location filter."""
    try:
        admin_db.delete_date_location_filter(filter_date)
        return HTMLResponse(f"""
            <h3>✅ Date filter for {filter_date} deleted successfully!</h3>
            <p><a href='/admin/date-filters'>Back to Date Filters</a></p>
        """)
    except Exception as e:
        return HTMLResponse(f"""
            <h3>❌ Error deleting date filter</h3>
            <p>Error: {str(e)}</p>
            <p><a href='/admin/date-filters'>Back to Date Filters</a></p>
        """)


@app.get("/api/date-filters")
async def get_date_filters():
    """API endpoint to get all date-based location filters."""
    return admin_db.get_all_date_location_filters()
