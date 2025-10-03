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

# Activate virtual environment (if needed)
source .venv/bin/activate
```

### Environment Setup
Copy `.env-example` to `.env` and configure:
- `STRAVA_CLIENT_ID` and `STRAVA_CLIENT_SECRET` - Strava OAuth credentials
- `STRAVA_REDIRECT_URI` - OAuth callback URL (default: `http://localhost:8000/callback`)
- `SECRET_KEY` - Session encryption key

## Architecture

### Database Layer (Specialized Classes)

The database layer uses two specialized classes in `src/databases/`:

**AdminDatabase** (`src/databases/admin_database.py`)
- Manages location configurations and date-specific location filters
- Tables: `settings`, `date_location_filters`
- Key method: `get_location_settings_for_activity(activity_start_date)` - returns location settings with date-specific overrides

**StravaDataDatabase** (`src/databases/strava_data_database.py`)
- Handles athletes, activities, GPS-based location filtering, and statistics
- Tables: `athletes`, `activities`
- Key methods:
  - `get_activities_filtered(athlete_id, admin_db, limit, activity_type)` - extracts relevant fields from raw JSON, filters by activity type, and applies GPS location matching
  - `get_athlete_stats(athlete_id, admin_db)` - calculates statistics; if `admin_db` provided, only counts activities matching location filters
  - `get_athlete_summary(athlete_id, admin_db)` - returns stats with sync status; if `admin_db` provided, stats are filtered by location

**Usage Pattern:**
```python
from src.databases import AdminDatabase, StravaDataDatabase

admin_db = AdminDatabase()
data_db = StravaDataDatabase()

# Get filtered activities with location matching
activities = data_db.get_activities_filtered(athlete_id, admin_db, limit=100, activity_type="Run")

# Each activity includes:
# - matches_location_filter: Boolean indicating if activity is within the filter radius
# - filter_info: Details about location, radius, distances, and filter source

# Get statistics filtered by location
summary = data_db.get_athlete_summary(athlete_id, admin_db)
# Returns: total_activities, total_distance, total_moving_time (all filtered by location)
```

**Important:** The app uses direct instantiation of `AdminDatabase` and `StravaDataDatabase` in `main.py`. These instances are passed to route setup functions. There is no unified database class - use the specialized classes directly.

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
- **Note:** Statistics and display logic belong in `StravaDataDatabase`, not in the sync service

### GPS-Based Location Filtering System

The application filters activities based on GPS proximity to configured locations:

**Default Location Settings** (in `settings` table):
- `target_latitude`, `target_longitude` - Default GPS coordinates (50.097416, 14.462274)
- `filter_radius_km` - Default search radius (1.0 km)

**Date-Specific Overrides** (in `date_location_filters` table):
- Activities on specific dates can use different coordinates
- Managed via `/admin/date-filters` interface
- Each filter has: date, latitude, longitude, radius, optional description
- Key method: `get_location_settings_for_activity(activity_date)` returns appropriate settings based on date

**How GPS Filtering Works:**
1. `StravaDataDatabase.get_activities_filtered()` extracts GPS coordinates from `raw_data` JSON
2. For each activity, gets location settings for its date (default or date-specific)
3. Uses Haversine formula (`calculate_distance()`) to calculate distances from start and end points to target location
4. Activity matches filter if BOTH start AND end points are within the radius
5. Adds `matches_location_filter` flag and `filter_info` dict to each activity
6. Dashboard highlights matching activities with green background

**Filtered Statistics:**
When `admin_db` is passed to `get_athlete_stats()` or `get_athlete_summary()`, statistics only include activities that match the location filter. This is used on the dashboard to show filtered stats alongside filtered activities.

**Visual Feedback:**
- Matching activities: Green background with checkmark badge
- Non-matching activities: Normal background with X badge
- Date-specific filters: Yellow "Date Filter" badge
- GPS Info column: Shows distances from start/end to target

**Current Activity Type Filter:** Only "Run" activities (hardcoded in `main_routes.py:36`)

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
        activities = data_db.get_activities_filtered(athlete_id, admin_db, limit=100, activity_type="Run")
        summary = data_db.get_athlete_summary(athlete_id, admin_db)
```

This pattern avoids global state and makes dependencies explicit. Note that `admin_db` is passed to both `get_activities_filtered()` and `get_athlete_summary()` to enable GPS location filtering for both activities and statistics.

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

2. **GPS Location Filtering:** The `get_activities_filtered()` method performs GPS filtering inline:
   - Extracts `start_latlng` and `end_latlng` from `raw_data` JSON
   - Gets location settings for activity date (default or date-specific override)
   - Calculates distances using Haversine formula
   - Requires BOTH start and end points within radius to match
   - Activities without GPS coordinates are marked as "No GPS"

3. **Filtered Statistics:** When `admin_db` is passed to `get_athlete_stats()` or `get_athlete_summary()`, the returned statistics only count activities that match the location filter. This ensures dashboard stats reflect only the filtered activities shown.

4. **Dashboard Display:** Dashboard shows 3 statistics (total activities, total distance, total moving time) - all filtered by location when `admin_db` is provided. Matching activities are highlighted with green background and show detailed distance information in the GPS Info column.

5. **Sync Strategy:** First-time login syncs from 2025-01-01. Subsequent syncs use latest activity date minus 1 day to catch updates.

6. **Database Path:** All database classes default to `strava_data.db` in the project root. Pass `db_path` parameter to use a different location.

7. **Templates:** Jinja2 templates in `templates/` directory. Dashboard template expects `summary.stats` with: `total_activities`, `total_distance`, `total_moving_time`.

## Separation of Concerns

**Data retrieval and display logic** belongs in `StravaDataDatabase`:
- `get_athlete_stats()` - calculate statistics
- `get_athlete_summary()` - combine stats with sync status
- `get_activities_filtered()` - retrieve and filter activities

**Synchronization logic** belongs in `ActivitySyncService`:
- `sync_athlete_activities()` - sync activities with Strava API
- `should_sync()` - determine if sync is needed
- `get_sync_start_date()` - calculate optimal sync date range

When adding new features, place data/stats methods in the database layer and sync/API methods in the sync service.
