"""
Admin routes: admin dashboard, settings, date filters
"""

from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.databases.admin_database import AdminDatabase
from src.databases.strava_data_database import StravaDataDatabase

templates = Jinja2Templates(directory="templates")


def setup_admin_routes(
    app: FastAPI, data_db: StravaDataDatabase, admin_db: AdminDatabase
) -> None:
    """Setup admin routes"""

    @app.get("/admin")
    async def admin_dashboard(request: Request):
        """Admin dashboard showing all athletes (for development)."""
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
