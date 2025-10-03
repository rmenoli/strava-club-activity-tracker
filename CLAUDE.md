# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A FastAPI web application that tracks Strava club activities with GPS-based filtering. Athletes authenticate via OAuth, sync their activities, and view filtered results based on configurable location criteria. Admins can manage date-specific location filters and view aggregate data across all athletes.

## Development Commands

### Running the Application
```bash
# Start the FastAPI development server
uvicorn main:app --reload --port 8000
```

### Dependency Management
```bash
# Install dependencies
uv sync

# Add a new dependency
uv add <package-name>

# Activate virtual environment
source .venv/bin/activate
```

### Environment Setup
Copy `.env-example` to `.env` and configure:
- `STRAVA_CLIENT_ID` and `STRAVA_CLIENT_SECRET` - Strava OAuth credentials
- `STRAVA_REDIRECT_URI` - OAuth callback URL (default: `http://localhost:8000/callback`)
- `SECRET_KEY` - Session encryption key

## Architecture

### Database Layer (Specialized Classes)

The database layer uses specialized classes in `src/databases/`:

**AdminDatabase** (`src/databases/admin_database.py`)
- Manages location configurations and date-specific location filters
- Tables: `settings`, `date_location_filters`
- Key method: `get_location_settings_for_activity(activity_start_date)` - returns location settings with date-specific overrides

**StravaDataDatabase** (`src/databases/strava_data_database.py`)
- Handles athletes, activities, and GPS-based filtering
- Tables: `athletes`, `activities`
- Key method: `get_activities_filtered(athlete_id, admin_db, limit, activity_type)` - extracts GPS data from raw JSON and applies inline filtering

**Usage Pattern:**
```python
from src.databases import AdminDatabase, StravaDataDatabase

admin_db = AdminDatabase()
data_db = StravaDataDatabase()

# GPS filtering happens inside get_activities_filtered
activities = data_db.get_activities_filtered(athlete_id, admin_db, limit=100, activity_type="Run")
```

**Important:** The app uses direct instantiation of `AdminDatabase` and `StravaDataDatabase` in `main.py`. These instances are passed to route setup functions.

### Route Organization

Routes are organized by functionality in `src/routes/`:

**main_routes.py**: User-facing routes
- `/` - Dashboard (shows filtered activities for logged-in athlete)
- `/login` - Strava OAuth login
- `/callback` - OAuth callback, syncs activities on first login
- `/sync` - Manual sync trigger
- `/download` - Export activities as CSV
- Session-based authentication using `request.session["athlete_id"]`

**admin_routes.py**: Administrative interface
- `/admin` - Multi-athlete dashboard with sync status
- `/admin/date-filters` - Manage date-specific location filters
- `/admin/date-filters/add` - Add new date filter (POST)
- `/admin/date-filters/delete/{date}` - Delete date filter (POST)
- `/api/date-filters` - JSON API for date filters

Both route modules are registered in `main.py` via `setup_main_routes(app, data_db, admin_db, sync_service)` and `setup_admin_routes(app, data_db, admin_db)`.

### Activity Sync Service

`ActivitySyncService` (`src/sync_service.py`) handles activity synchronization:
- Accepts any database instance with the required methods (`needs_sync`, `get_athlete_last_sync`, etc.)
- Determines when sync is needed (max age: 1 hour)
- Intelligently calculates sync start date based on last sync and latest activity
- Called during OAuth callback for initial sync
- Available via manual `/sync` endpoint

### GPS Filtering System

Activities are filtered by proximity to target coordinates with date-specific overrides:

**Default Location Settings** (in `settings` table):
- `target_latitude`, `target_longitude` - Default GPS coordinates (50.097416, 14.462274)
- `filter_radius_km` - Default search radius (1.0 km)

**Date-Specific Overrides** (in `date_location_filters` table):
- Activities on specific dates use override coordinates
- Managed via `/admin/date-filters` interface
- Each filter has: date, latitude, longitude, radius, optional description

**Filtering Implementation:**
- Happens inline within `StravaDataDatabase.get_activities_filtered()`
- Extracts GPS coordinates from `raw_data` JSON field
- Uses `admin_db.get_location_settings_for_activity(activity_date)` to get date-specific or default settings
- Applies Haversine formula to calculate distances
- Filters where BOTH start and end points are within radius
- **Current filter:** Only "Run" activities (hardcoded in `main_routes.py:36`)

## Key Patterns

### Database Initialization

```python
# In main.py
from src.databases.admin_database import AdminDatabase
from src.databases.strava_data_database import StravaDataDatabase
from src.sync_service import ActivitySyncService

admin_db = AdminDatabase()  # Initializes settings and date_location_filters tables
data_db = StravaDataDatabase()  # Initializes athletes and activities tables
sync_service = ActivitySyncService(data_db)
```

### OAuth Token Management

Tokens are stored in two places:
1. **Session storage**: For active web sessions (`request.session["athlete_id"]`)
2. **File storage**: `strava_tokens.json` for persistent storage and manual sync

Token lifecycle:
- OAuth callback: Stores tokens in both session and file
- Activity fetch: `StravaClient.ensure_valid_token()` automatically refreshes if expired
- Manual sync: `ActivitySyncService.sync_athlete_with_stored_tokens()` loads from file

**Important:** Refresh tokens are rotated by Strava on each refresh - always save updated tokens.

### Route Setup Pattern

Routes use dependency injection via closure:
```python
def setup_main_routes(app, data_db, admin_db, sync_service):
    @app.get("/")
    async def index(request: Request):
        # Has access to data_db, admin_db, sync_service via closure
        activities = data_db.get_activities_filtered(athlete_id, admin_db)
```

This pattern avoids global state and makes dependencies explicit.

## Database Schema

### Core Tables

**athletes**
- `athlete_id` (TEXT, PK) - Strava athlete ID (string)
- `first_name`, `last_name` - Athlete names
- `last_sync` (TIMESTAMP) - Last successful sync time
- `total_activities` (INTEGER) - Cached activity count

**activities**
- `activity_id` (INTEGER, PK) - Strava activity ID
- `athlete_id` (TEXT, FK) - References athletes
- `name`, `type`, `start_date` - Basic activity info
- `distance`, `moving_time`, `elapsed_time` - Performance metrics
- `total_elevation_gain`, `average_speed`, `max_speed` - Additional stats
- `raw_data` (TEXT) - Full Strava API response as JSON (includes `start_latlng` and `end_latlng`)

**settings**
- `key` (TEXT, PK) - Setting name
- `value` (TEXT) - Setting value (always stored as string)
- Default keys: `target_latitude`, `target_longitude`, `filter_radius_km`

**date_location_filters**
- `filter_date` (DATE, UNIQUE) - Date for location override (YYYY-MM-DD)
- `target_latitude`, `target_longitude`, `radius_km` - Override coordinates
- `description` (TEXT) - Optional description

### Important Indexes
- `idx_athlete_activities` on `activities(athlete_id, start_date)`
- `idx_activity_date` on `activities(start_date)`
- `idx_date_filters_date` on `date_location_filters(filter_date)`

## Session Management

Uses Starlette's `SessionMiddleware` with cookie-based sessions:
- Session data encrypted in cookies (no server-side storage)
- `athlete_id` stored in session after OAuth
- Session cleared on `/logout`

## Activity Data Structure

The `raw_data` field in activities table contains the full Strava API response as JSON:
```python
raw_data = json.loads(activity["raw_data"])
start_latlng = raw_data.get("start_latlng")  # [latitude, longitude]
end_latlng = raw_data.get("end_latlng")      # [latitude, longitude]
```

In `get_activities_filtered()`, these fields are extracted and added to each activity dict for filtering.

## Strava API Integration

**Rate Limits:**
- 100 requests per 15 minutes
- 1000 requests per day
- Code includes 0.2s delay between paginated requests

**OAuth Scopes:**
- `activity:read_all` - Access all activities (main requirement)

**Token Refresh:**
- Automatic via `StravaClient.ensure_valid_token()`
- Handles 401 errors with automatic retry
- Updates refresh token after each refresh (Strava rotates them)
- Save updated tokens via `save_tokens()` from `src/store_token.py`

## Important Implementation Details

1. **Activity Type Filtering:** Currently hardcoded to "Run" in `main_routes.py:36`. Change the `activity_type` parameter to filter different activity types or remove it to show all.

2. **GPS Filtering:** Inline within `get_activities_filtered()`. The method extracts GPS coords from JSON, gets location settings from admin_db, and filters in a single operation.

3. **Sync Strategy:** First-time login syncs from 2025-01-01. Subsequent syncs use latest activity date minus 1 day to catch updates.

4. **Database Path:** All database classes default to `strava_data.db` in the project root. Pass `db_path` parameter to use a different location.

5. **Templates:** Jinja2 templates in `templates/` directory. Currently 5 templates: `index.html`, `dashboard.html`, `admin.html`, `admin_date_filters.html`, `admin_settings.html` (last one unused after recent refactor).

## Testing with Jupyter

The `notebooks/` directory contains Jupyter notebooks for data analysis. Notebooks reference the StravaDatabase class but this is only for documentation - actual analysis uses pandas with direct SQLite queries.
