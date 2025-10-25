# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A FastAPI web application that tracks Strava club activities with GPS-based filtering. Athletes authenticate via OAuth, sync their activities, and view filtered results based on configurable location criteria. Admins can manage date-specific location filters and view aggregate data across all athletes.

**Tech Stack:** FastAPI, PostgreSQL, Jinja2 templates, vanilla CSS (no frontend framework)

## Development Commands

### Database Setup
```bash
# Start PostgreSQL via Docker Compose
docker-compose up -d

# Stop PostgreSQL
docker-compose down

# Stop and remove all data
docker-compose down -v
```

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

### Testing
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_activities_filtered.py

# Run specific test class
pytest tests/test_activities_filtered.py::TestGetActivitiesFiltered

# Run specific test
pytest tests/test_activities_filtered.py::TestGetActivitiesFiltered::test_location_filtering_with_default_settings_match

# Run with verbose output
pytest -v

# Run with coverage report
pytest --cov=src --cov-report=html
```

### Deployment

**Production Deployment (AWS EC2):**
```bash
# On EC2 instance after SSH
bash scripts/setup_ec2.sh  # Automated setup: Docker, firewall, etc.

# Configure environment
cp .env.example.production .env
vim .env  # Update with production values

# Deploy with Docker Compose
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Restart services
docker-compose -f docker-compose.prod.yml restart
```

See `DEPLOYMENT.md` for comprehensive deployment guide including AWS setup, security groups, Elastic IP allocation, and troubleshooting.

**Test Infrastructure:**
- Tests use a separate PostgreSQL database (`strava_tracker_test`) to avoid affecting development data
- Test database is automatically created on first test run
- `tests/conftest.py` provides shared fixtures and test configuration
- All test environment variables are loaded from `tests/.env.test` at module level with `override=True`
- Each test gets a clean database state via fixture cleanup

### Environment Setup
Copy `.env-example` to `.env` and configure:
- `STRAVA_CLIENT_ID` and `STRAVA_CLIENT_SECRET` - Strava OAuth credentials (required)
- `STRAVA_REDIRECT_URI` - OAuth callback URL (optional, default: `http://localhost:8000/auth/strava/callback`)
- `SECRET_KEY` - Session encryption key (optional, default: `dev-secret`)
- `DATABASE_URL` - PostgreSQL connection string (required)
- `ADMIN_ATHLETE_IDS` - Comma-separated list of Strava athlete IDs with admin access (optional, default: empty)

**Configuration Management:**
All environment variables are loaded and validated at application startup using a centralized `Config` class (`src/config.py`). Missing required variables will cause the application to exit immediately with a clear error message listing what's missing. This eliminates runtime configuration errors and ensures all required settings are present before the application starts.

## Architecture

### Configuration Management

The application uses a centralized configuration system (`src/config.py`) built with `python-dotenv`:

**Config Class:**
- Uses `load_dotenv()` to load `.env` file at startup
- Validates required fields (DATABASE_URL, STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET)
- Provides type-annotated access to configuration values
- Fails fast with helpful error messages if validation fails

**Implementation:**
```python
class Config:
    def __init__(self):
        load_dotenv()  # Load .env file
        self.DATABASE_URL = self._get_required("DATABASE_URL")
        self.STRAVA_CLIENT_ID = self._get_required("STRAVA_CLIENT_ID")
        # ... validates required vars, exits if missing
```

**Usage Pattern:**
```python
from src.config import load_config

# Load and validate configuration (in main.py)
config = load_config()  # Exits if validation fails

# Access configuration values
database_url = config.DATABASE_URL
client_id = config.STRAVA_CLIENT_ID
```

**Benefits:**
- Single source of truth for all environment variables
- Validation happens once at startup, not scattered throughout the code
- Type-annotated configuration access for IDE support
- Clear error messages for missing configuration
- No external dependencies beyond python-dotenv (already installed)

### Database Layer (Specialized Classes)

The database layer uses two specialized classes in `src/databases/`:

**AdminDatabase** (`src/databases/admin_database.py`)
- Manages location configurations, date-specific location filters, general settings, and discount rewards
- Tables: `settings`, `date_location_filters`, `discounts`
- Key methods:
  - `get_location_settings_for_activity(activity_start_date)` - returns location settings with date-specific overrides
  - `get_activity_filter_days()` - returns the configured number of days for activity history filtering
  - `update_activity_filter_days(days)` - updates the time period filter setting
  - `get_discount_threshold()` - returns the minimum activities required for discount access
  - `update_discount_threshold(threshold)` - updates the discount threshold setting
  - `get_all_discounts(active_only)` - returns all discounts (optionally filtered by active status)
  - `get_active_discounts()` - returns only active discounts for user display
  - `add_discount(title, description, code)` - creates a new discount
  - `delete_discount(discount_id)` - deletes a discount
  - `toggle_discount_status(discount_id)` - toggles discount active/inactive status

**StravaDataDatabase** (`src/databases/strava_data_database.py`)
- Handles athletes, activities, GPS-based location filtering, and statistics
- Tables: `athletes`, `activities`
- Key methods:
  - `get_activities_filtered(athlete_id, admin_db, limit)` - extracts relevant fields from raw JSON and applies GPS location matching
  - `get_athlete_stats(athlete_id, admin_db)` - calculates statistics; if `admin_db` provided, only counts activities matching location filters
  - `get_athlete_summary(athlete_id, admin_db)` - returns stats with sync status; if `admin_db` provided, stats are filtered by location

**Usage Pattern:**
```python
from src.config import load_config
from src.databases import AdminDatabase, StravaDataDatabase

# Load configuration (validates all required env vars)
config = load_config()

# Initialize databases
admin_db = AdminDatabase(config.DATABASE_URL)
data_db = StravaDataDatabase(config.DATABASE_URL)

# Get filtered activities with location matching
activities = data_db.get_activities_filtered(athlete_id, admin_db, limit=100)

# Each activity includes:
# - matches_location_filter: Boolean indicating if activity is within the filter radius
# - filter_info: Details about location, radius, distances, and filter source

# Get statistics filtered by location
summary = data_db.get_athlete_summary(athlete_id, admin_db)
# Returns: total_activities, total_distance, total_moving_time (all filtered by location)
```

**Important:** Both database classes require a `DATABASE_URL` parameter (PostgreSQL connection string). Use the centralized `Config` class to load and validate configuration - the app will fail immediately with a helpful error if any required environment variable is missing. There is no SQLite fallback - use the specialized classes directly with PostgreSQL.

### Route Organization

Routes are organized by functionality in `src/routes/`:

**main_routes.py**: User-facing routes
- `/` - Dashboard (shows filtered activities for logged-in athlete)
- `/login` - Strava OAuth login
- `/auth/strava/callback` - OAuth callback, syncs activities on first login
- `/sync` - Manual sync trigger
- `/download` - Export activities as CSV
- `/discounts` - Rewards page for athletes meeting the configurable activity threshold
- `/logout` - Clear session and redirect to home
- Session-based authentication using `request.session["athlete_id"]`

**admin_routes.py**: Administrative interface (requires admin authentication)
- `/admin` - Multi-athlete dashboard with sync status
- `/admin/settings` - General settings management (activity filter days, discount threshold)
- `/admin/settings/update` - Update general settings (POST)
- `/admin/date-filters` - Manage date-specific location filters
- `/admin/date-filters/add` - Add new date filter (POST)
- `/admin/date-filters/delete/{date}` - Delete date filter (POST)
- `/api/date-filters` - JSON API for date filters
- `/admin/discounts` - Discount management interface
- `/admin/discounts/add` - Create new discount (POST)
- `/admin/discounts/delete/{discount_id}` - Delete discount (POST)
- `/admin/discounts/toggle/{discount_id}` - Toggle discount active/inactive status (POST)

**Admin Authentication:**
All admin routes are protected by whitelist-based authentication (`src/auth.py`):
- Checks if logged-in athlete's ID is in `ADMIN_ATHLETE_IDS` environment variable
- Non-authenticated users are redirected to `/login`
- Authenticated non-admins receive a 403 Forbidden response
- Admin status is checked on every request (no caching)
- Changes to admin list require application restart

Both route modules are registered in `main.py` via `setup_main_routes(app, data_db, admin_db, sync_service, config)` and `setup_admin_routes(app, data_db, admin_db, config)`.

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
- `activity_filter_days` - Number of days of activity history to include in statistics (default: 90)
- `discount_threshold_activities` - Minimum activities required for discount access (default: 5)

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

**Filtered Statistics (Time + Location):**
When `admin_db` is passed to `get_athlete_stats()` or `get_athlete_summary()`, statistics are filtered by:
1. **Time period**: Only activities within the last N days (configurable via `activity_filter_days` setting in `/admin/settings`)
2. **Location**: Only activities matching the GPS location filter (start AND end points within radius)

This two-level filtering ensures dashboard stats reflect only relevant, recent activities that match the configured location criteria. The time filter is displayed in the dashboard title (e.g., "Activities With PRC (Last 90 days)").

**Visual Feedback:**
- Matching activities: Green background with checkmark badge
- Non-matching activities: Normal background with X badge
- Date-specific filters: Yellow "Date Filter" badge
- GPS Info column: Shows distances from start/end to target

**Current Activity Type Filter:** Only "Run" activities (hardcoded in SQL query at `strava_data_database.py:516`)

## Key Patterns

### Database Initialization

```python
# In main.py
from src.config import load_config
from src.databases.admin_database import AdminDatabase
from src.databases.strava_data_database import StravaDataDatabase
from src.sync_service import ActivitySyncService

# Load and validate configuration - exits if any required env vars are missing
config = load_config()

# Initialize database and sync service
admin_db = AdminDatabase(config.DATABASE_URL)  # Initializes settings and date_location_filters tables
data_db = StravaDataDatabase(config.DATABASE_URL)  # Initializes athletes and activities tables
sync_service = ActivitySyncService(data_db, config)  # Needs config for Strava API credentials
```

### OAuth Token Management

Tokens are stored in two places:
1. **Session storage**: For active web sessions (`request.session["athlete_id"]`)
2. **Database storage**: In the `athletes` table (`access_token`, `refresh_token`, `token_expires_at` columns)

Token lifecycle:
- OAuth callback: Stores tokens in both session and database via `data_db.save_athlete_tokens()`
- Activity fetch: `StravaClient.ensure_valid_token()` automatically refreshes if expired
- Manual sync: `ActivitySyncService.sync_athlete_with_stored_tokens()` loads from database
- Token refresh: Updated tokens are automatically saved back to database after each sync

**Important:** Refresh tokens are rotated by Strava on each refresh - the sync service automatically saves updated tokens to the database after each sync operation.

### Route Setup Pattern

Routes use dependency injection via closure:
```python
def setup_main_routes(app, data_db, admin_db, sync_service, config):
    @app.get("/")
    async def index(request: Request):
        # Has access to data_db, admin_db, sync_service, config via closure
        activities = data_db.get_activities_filtered(athlete_id, admin_db, limit=100)
        summary = data_db.get_athlete_summary(athlete_id, admin_db)

    @app.get("/login")
    async def login():
        # Can access Strava credentials from config
        auth_url = f"https://www.strava.com/oauth/authorize?client_id={config.STRAVA_CLIENT_ID}..."
```

This pattern avoids global state and makes dependencies explicit. Configuration values are accessed through the `config` parameter, which provides type-safe access to environment variables. Note that `admin_db` is passed to both `get_activities_filtered()` and `get_athlete_summary()` to enable GPS location filtering for both activities and statistics.

### Static Files and Frontend

**Static File Serving:**
```python
# In main.py
from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory="static"), name="static")
```

**Directory Structure:**
```
static/
  css/
    style.css  # Consolidated styles for all templates (930+ lines)
templates/
  index.html              # Welcome/login page
  dashboard.html          # User activity dashboard
  admin.html              # Admin multi-athlete view
  admin_settings.html     # General settings (activity filter days, discount threshold)
  admin_date_filters.html # Date-specific location filter management
  admin_discounts.html    # Discount management interface (CRUD operations)
  discount.html           # Rewards/discounts page with card-based display
```

**CSS Architecture:**
- All templates link to `/static/css/style.css` (no inline styles)
- Organized into sections: reset, typography, containers, navigation, buttons, stats, tables, forms, filters, responsive
- Uses page-specific body classes: `welcome-page`, `dashboard-page`
- Color scheme: Strava orange (#fc4c02) on dark background (#2c2c2c)
- Responsive breakpoints: 1200px (tablet), 768px (mobile)

**Template Pattern:**
```html
<!DOCTYPE html>
<html>
<head>
    <title>Page Title</title>
    <link rel="stylesheet" href="/static/css/style.css">
</head>
<body class="page-specific-class">
    <!-- Jinja2 template content -->
</body>
</html>
```

**When modifying styles:**
- Edit `static/css/style.css` (affects all pages)
- Use existing CSS classes when possible
- Add page-specific classes to body element for page-specific overrides
- Browser caching: CSS is cached after first load

## Database Schema

**Database:** PostgreSQL (required, no SQLite fallback)

### Core Tables

**athletes**
- `athlete_id` (TEXT, PK) - Strava athlete ID (string)
- `first_name`, `last_name` - Athlete names
- `last_sync` (TIMESTAMP) - Last successful sync time
- `total_activities` (INTEGER) - Cached activity count
- `access_token` (TEXT) - Strava OAuth access token
- `refresh_token` (TEXT) - Strava OAuth refresh token
- `token_expires_at` (BIGINT) - Token expiration timestamp (Unix epoch)

**activities**
- `activity_id` (BIGINT, PK) - Strava activity ID
- `athlete_id` (TEXT, FK) - References athletes
- `name`, `type`, `start_date` - Basic activity info
- `distance`, `moving_time`, `elapsed_time` - Performance metrics
- `total_elevation_gain`, `average_speed`, `max_speed` - Additional stats
- `raw_data` (TEXT) - Full Strava API response as JSON (includes `start_latlng` and `end_latlng`)

**settings**
- `key` (TEXT, PK) - Setting name
- `value` (TEXT) - Setting value (always stored as string)
- Default keys: `target_latitude`, `target_longitude`, `filter_radius_km`, `activity_filter_days`, `discount_threshold_activities`

**date_location_filters**
- `id` (SERIAL, PK) - Auto-incrementing ID
- `filter_date` (DATE, UNIQUE) - Date for location override (YYYY-MM-DD)
- `target_latitude`, `target_longitude`, `radius_km` - Override coordinates
- `description` (TEXT) - Optional description

**discounts**
- `id` (SERIAL, PK) - Auto-incrementing ID
- `title` (TEXT, required) - Discount title/name
- `description` (TEXT) - Detailed description of the discount
- `code` (TEXT, required) - Discount code for redemption
- `is_active` (BOOLEAN) - Whether discount is currently active (default: TRUE)
- `created_at`, `updated_at` (TIMESTAMP) - Tracking timestamps

### Important Indexes
- `idx_athlete_activities` on `activities(athlete_id, start_date)`
- `idx_activity_date` on `activities(start_date)`
- `idx_date_filters_date` on `date_location_filters(filter_date)`

### SQL Syntax Notes
The codebase uses PostgreSQL-specific syntax:
- Placeholders: `%s` (not `?`)
- UPSERT: `INSERT ... ON CONFLICT ... DO UPDATE SET`
- Auto-increment: `SERIAL` or `BIGINT` with sequences
- All queries use `psycopg2` with `RealDictCursor` for dict-like row access

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
- Refreshed tokens are automatically saved to database by `ActivitySyncService` after each sync

## Important Implementation Details

1. **Activity Type Filtering:** Currently hardcoded to "Run" in the SQL query at `strava_data_database.py:516`. To show different activity types, modify the WHERE clause in `get_activities_filtered()` method (e.g., change `AND type = 'Run'` to `AND type = 'Ride'` or remove the type filter entirely).

2. **GPS Location Filtering:** The `get_activities_filtered()` method performs GPS filtering inline:
   - Extracts `start_latlng` and `end_latlng` from `raw_data` JSON
   - Gets location settings for activity date (default or date-specific override)
   - Calculates distances using Haversine formula
   - Requires BOTH start and end points within radius to match
   - Activities without GPS coordinates are marked as "No GPS"

3. **Filtered Statistics:** When `admin_db` is passed to `get_athlete_stats()` or `get_athlete_summary()`, the returned statistics are filtered by:
   - **Time**: Only includes activities from the last N days (configured in `activity_filter_days` setting)
   - **Location**: Only includes activities matching the GPS location filter

   This two-level filtering ensures dashboard stats reflect only relevant, recent activities.

4. **Dashboard Display:** Dashboard shows 3 statistics (total activities, total distance, total moving time) - all filtered by time period and location when `admin_db` is provided. The time period is shown in the stats title (e.g., "Activities With PRC (Last 90 days)"). Matching activities are highlighted with green background and show detailed distance information in the GPS Info column.

5. **Conditional Features:** The dashboard includes conditional UI elements based on activity count:
   - Athletes with activity count >= configurable threshold (default: 5) see a "Visualize Discounts" button linking to `/discounts`
   - The discounts page displays active discounts configured by admins via `/admin/discounts`

6. **Sync Strategy:** First-time login syncs from 180 days ago (6 months). Subsequent syncs use latest activity date minus 1 day to catch updates.

7. **Configuration Validation:** All required environment variables (DATABASE_URL, STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET) are validated at application startup via the `Config` class. The app will fail immediately with a helpful error message if any required configuration is missing - no fallback or runtime errors.

8. **Activity Time Filter:** The time period for filtering activities in statistics is configurable via the admin settings (`/admin/settings`). Default is 90 days, but can be set to any value between 1-365 days. This allows flexibility for different use cases (weekly, monthly, quarterly, or annual tracking).

9. **Templates & Static Files:**
   - Jinja2 templates in `templates/` directory
   - All styles consolidated in `static/css/style.css`
   - Dashboard template expects `summary.stats` with: `total_activities`, `total_distance`, `total_moving_time`
   - Dashboard template expects `activity_filter_days` to display the time period in the stats title
   - Templates use external CSS (no inline `<style>` blocks)

10. **Admin Access Management:**
   - Admin access is controlled via the `ADMIN_ATHLETE_IDS` environment variable (comma-separated list)
   - To grant admin access: add athlete's Strava ID to the list and restart the application
   - To find athlete IDs: check the `athletes` table in the database or inspect session data
   - All `/admin` routes are protected by `require_admin()` function from `src/auth.py`
   - Non-admins attempting to access admin routes receive a 403 Forbidden response
   - Empty `ADMIN_ATHLETE_IDS` means no one has admin access (secure default)
   - Changes to the admin list require application restart to take effect

## Separation of Concerns

**Data retrieval and display logic** belongs in `StravaDataDatabase`:
- `get_athlete_stats()` - calculate statistics
- `get_athlete_summary()` - combine stats with sync status
- `get_activities_filtered()` - retrieve and filter activities

**Synchronization logic** belongs in `ActivitySyncService`:
- `sync_athlete_activities()` - sync activities with Strava API
- `should_sync()` - determine if sync is needed
- `get_sync_start_date()` - calculate optimal sync date range

**Presentation logic** belongs in templates and CSS:
- Jinja2 templates in `templates/` handle HTML structure
- `static/css/style.css` handles all styling (no inline styles)
- Templates receive data from routes, routes get data from database layer

When adding new features:
- Data/stats methods → `StravaDataDatabase`
- Sync/API methods → `ActivitySyncService`
- Route handlers → `src/routes/`
- Visual styling → `static/css/style.css`
- HTML structure → `templates/`

## Recent Enhancements

### Configurable Activity Time Filter (Latest)
The application now allows admins to configure the time period for activity filtering:
- **Setting**: `activity_filter_days` in the `settings` table (default: 90 days)
- **Management**: `/admin/settings` page with form to update the value (1-365 days range)
- **Implementation**: `StravaDataDatabase.get_athlete_stats()` reads this setting via `admin_db.get_activity_filter_days()`
- **Display**: Dashboard title shows the current time period (e.g., "Activities With PRC (Last 90 days)")
- **Purpose**: Allows flexible time-based filtering for different use cases (weekly reviews, monthly reports, seasonal tracking)

### Discount Management System (Latest)
Full-featured discount/rewards system with admin management and user display:
- **Database**: `discounts` table with fields: id, title, description, code, is_active, created_at, updated_at
- **Admin Interface**: `/admin/discounts` with full CRUD operations
  - Add discounts with title, description, and redemption code
  - Toggle active/inactive status without deletion
  - Delete discounts permanently
  - View all discounts with status indicators
- **User Interface**: `/discounts` page displays active discounts in card-based grid layout
  - Each card shows title, description, and discount code
  - Empty state message when no discounts available
- **Access Control**: Configurable threshold (`discount_threshold_activities` in settings table)
  - Dashboard button enabled when athlete has >= threshold activities
  - Dashboard button disabled with unlock message when below threshold
- **Implementation Details**:
  - AdminDatabase methods: `get_all_discounts()`, `get_active_discounts()`, `add_discount()`, `delete_discount()`, `toggle_discount_status()`
  - User route fetches only active discounts via `admin_db.get_active_discounts()`
  - Responsive card layout with hover effects
  - Discount codes displayed in monospace font via `<code>` element

### Key Implementation Details
1. **Two-Level Filtering**: Statistics are now filtered by both time period (configurable days) AND GPS location (proximity-based)
2. **Dynamic Dashboard**: Time period and discount threshold are passed from route to template and displayed dynamically
3. **Admin Control**: All filtering parameters (location, radius, time period, discount threshold) are now configurable via admin interface
4. **Backward Compatibility**: If `admin_db` is not provided to stats methods, defaults to 90 days for time filtering
5. **Gamification**: Discount button always visible but disabled state motivates athletes to reach the threshold

## Testing Strategy

### Test Organization

**Integration Tests** (`tests/` directory):
- `test_activities_filtered.py` - Comprehensive tests for `get_activities_filtered()` method
  - Tests basic retrieval without location filtering
  - Tests GPS location matching (both matching and non-matching cases)
  - Tests date-specific location overrides
  - Tests edge cases (no GPS data, empty results, ordering, limits)
  - 9 test cases covering all major scenarios

**Test Fixtures** (`tests/conftest.py`):
- `test_config` - Test configuration that loads from `tests/.env.test`
- `setup_test_database` - Session-scoped fixture that creates/drops test database
- `admin_db` - Function-scoped AdminDatabase with automatic cleanup
- `data_db` - Function-scoped StravaDataDatabase with automatic cleanup
- `sync_service` - ActivitySyncService instance for testing
- `mock_strava_client` - Mock Strava API client to avoid real API calls
- `sample_activity`, `sample_activity_far`, `sample_activity_no_gps` - Sample activity data
- `create_test_athlete`, `create_test_activity`, `create_date_filter` - Factory fixtures

**Important Test Configuration Details:**
1. Environment variables are loaded from `tests/.env.test` with `override=True` at module level (before Config is instantiated)
2. The `Config` class automatically picks up test environment variables without manual overrides
3. Each test gets a clean database state via fixture teardown
4. Settings are reset to defaults after each test (activity_filter_days=90, discount_threshold_activities=5, etc.)
5. The test database persists between test runs for performance (manually reset with `docker-compose down -v`)
6. **Critical:** Activities must be stored with valid JSON in `raw_data` field using `json.dumps()`, not `str()`

**Writing New Tests:**
```python
def test_my_feature(data_db, admin_db, create_test_athlete, create_test_activity):
    """Test description."""
    # Setup
    athlete_id = create_test_athlete()
    activity = {"id": 1001, "name": "Test Run", "type": "Run", ...}
    create_test_activity(athlete_id, activity)

    # Execute
    result = data_db.get_activities_filtered(athlete_id, admin_db)

    # Verify
    assert len(result) == 1
    assert result[0]["name"] == "Test Run"
```

**Key Testing Patterns:**
- Use factory fixtures (`create_test_*`) to create test data
- Pass `admin_db` to enable GPS location filtering in tests
- Sample activities use Prague coordinates (50.097416, 14.462274) for matching tests
- Sample activities use London coordinates (51.5074, -0.1278) for non-matching tests
- Activities must have `type='Run'` to be returned by `get_activities_filtered()`

**Test Coverage:**
- Database operations (CRUD)
- GPS distance calculations (Haversine formula)
- Location filtering logic (both start AND end points must be within radius)
- Date-specific location overrides
- Activity ordering and pagination
- Edge cases (missing GPS, empty results, etc.)
