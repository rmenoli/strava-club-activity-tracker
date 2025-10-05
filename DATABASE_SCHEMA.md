# Database Schema

## Entity Relationship Diagram

```mermaid
erDiagram
    athletes ||--o{ activities : "has many"

    athletes {
        TEXT athlete_id PK "Strava athlete ID"
        TEXT first_name "Athlete first name"
        TEXT last_name "Athlete last name"
        TIMESTAMP created_at "Account creation time"
        TIMESTAMP last_sync "Last activity sync time"
        INTEGER total_activities "Cached activity count"
        TEXT access_token "Strava OAuth access token"
        TEXT refresh_token "Strava OAuth refresh token"
        BIGINT token_expires_at "Token expiration (Unix timestamp)"
    }

    activities {
        BIGINT activity_id PK "Strava activity ID"
        TEXT athlete_id FK "References athletes"
        TEXT name "Activity name"
        TEXT type "Activity type (Run, Ride, etc)"
        TEXT start_date "Activity start timestamp"
        REAL distance "Distance in meters"
        INTEGER moving_time "Moving time in seconds"
        INTEGER elapsed_time "Total elapsed time"
        REAL total_elevation_gain "Elevation gain in meters"
        REAL average_speed "Average speed m/s"
        REAL max_speed "Max speed m/s"
        TEXT raw_data "Full Strava API response (JSON)"
        TIMESTAMP created_at "Record creation time"
    }

    settings {
        TEXT key PK "Setting key"
        TEXT value "Setting value"
        TEXT description "Setting description"
        TIMESTAMP updated_at "Last update time"
    }

    date_location_filters {
        SERIAL id PK "Auto-incrementing ID"
        DATE filter_date UK "Date for override (UNIQUE)"
        REAL target_latitude "Override latitude"
        REAL target_longitude "Override longitude"
        REAL radius_km "Override radius in km"
        TEXT description "Filter description"
        TIMESTAMP created_at "Record creation time"
        TIMESTAMP updated_at "Last update time"
    }
```

## Table Descriptions

### athletes
**Purpose:** Stores athlete profiles and OAuth tokens for API access.

**Key Features:**
- Primary authentication and identity table
- Stores Strava OAuth tokens in database (moved from file storage)
- Tracks sync status and activity count
- One athlete can have many activities

**Indexes:**
- Primary Key on `athlete_id`

---

### activities
**Purpose:** Stores individual Strava activities with full API data.

**Key Features:**
- Linked to athletes via foreign key
- Structured columns for common queries
- `raw_data` JSON column preserves complete Strava response
- Used for GPS-based location filtering

**Indexes:**
- Primary Key on `activity_id`
- `idx_athlete_activities` on `(athlete_id, start_date)` - for user queries
- `idx_activity_date` on `start_date` - for date-based filtering

**Relationships:**
- Many-to-One with `athletes` table

---

### settings
**Purpose:** Application-wide configuration values.

**Key Features:**
- Key-value storage for app settings
- Default location coordinates (latitude, longitude)
- Default filter radius
- Standalone table (no relationships)

**Default Values:**
- `target_latitude`: 50.097416 (Prague)
- `target_longitude`: 14.462274
- `filter_radius_km`: 1.0

---

### date_location_filters
**Purpose:** Date-specific location overrides for activity filtering.

**Key Features:**
- Allows different GPS filters for specific dates
- Overrides default location settings from `settings` table
- Useful for events at different locations
- Standalone table (no relationships)

**Indexes:**
- Primary Key on `id` (auto-increment)
- Unique constraint on `filter_date`
- `idx_date_filters_date` on `filter_date` - for date lookups

---

## Relationships

### One-to-Many: athletes → activities
- Each athlete can have multiple activities
- Foreign key: `activities.athlete_id` → `athletes.athlete_id`
- Cascade behavior: Not defined (manual cleanup required)

### No Direct Relationships
- `settings` and `date_location_filters` are standalone configuration tables
- Referenced programmatically but no database-level foreign keys

---

## Data Flow

1. **Authentication Flow:**
   ```
   Strava OAuth → athletes table (saves tokens)
   ```

2. **Activity Sync Flow:**
   ```
   Strava API → activities table → linked to athletes
   Token refresh → updates athletes.access_token & refresh_token
   ```

3. **Location Filtering:**
   ```
   Activity date → check date_location_filters
   If no date filter → use settings table defaults
   Apply GPS filtering → activity.raw_data (start_latlng, end_latlng)
   ```

---

## Database Type

**PostgreSQL** (version 16 recommended)

- No SQLite fallback
- Uses PostgreSQL-specific features:
  - `SERIAL` for auto-increment
  - JSON operators (`->>`, `->`)
  - `DO $$` blocks for migrations
  - `ON CONFLICT` for upserts

---

## Migration Strategy

Token columns added in recent update:
- `ALTER TABLE` statements added to `init_data_tables()`
- Checks for column existence before adding
- Graceful migration for existing databases
- No data loss on upgrade
