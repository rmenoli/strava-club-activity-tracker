# Database Refactoring Documentation

## Overview

The `StravaDatabase` class has been refactored into a modular architecture with specialized database classes organized in a dedicated `databases` folder:

1. **`AdminDatabase`** - Handles admin-related operations (settings, date filters)
2. **`StravaDataDatabase`** - Handles core data operations (athletes, activities, GPS filtering)

## New File Structure

```
src/
├── databases/               # Dedicated databases folder
│   ├── __init__.py          # Database package exports
│   ├── admin_database.py    # AdminDatabase class
│   └── strava_data_database.py  # StravaDataDatabase class
├── routes/
│   ├── __init__.py
│   ├── admin_routes.py
│   └── main_routes.py
├── store_token.py
├── strava_client.py
└── sync_service.py
```

## Architecture

### 1. AdminDatabase (`src/databases/admin_database.py`)

**Purpose**: Manages admin configurations, settings, and date-based location filters.

**Responsibilities**:
- Global settings management (`get_setting`, `set_setting`, `get_all_settings`)
- Location settings management (`get_location_settings`, `update_location_settings`)
- Date-based location filters (`add_date_location_filter`, `get_date_location_filter`, etc.)
- Admin-specific database table initialization

**Database Tables**:
- `settings` - Global configuration settings
- `date_location_filters` - Date-specific location filters

### 2. StravaDataDatabase (`src/databases/strava_data_database.py`)

**Purpose**: Manages core Strava data including athletes, activities, and GPS-based filtering.

**Responsibilities**:
- Athlete management (`upsert_athlete`, `get_all_athletes`, `get_athlete_stats`)
- Activity management (`save_activities`, `get_activities`, `get_activities_filtered`)
- GPS filtering logic (`filter_activities`)
- Core data table initialization

**Database Tables**:
- `athletes` - Athlete information and sync status
- `activities` - Activity data with GPS coordinates

## Usage Examples

### Direct Import from Specific Modules

```python
# Import from the databases package
from src.databases.admin_database import AdminDatabase
from src.databases.strava_data_database import StravaDataDatabase

# Use AdminDatabase for admin operations
admin_db = AdminDatabase()
admin_db.add_date_location_filter("2025-01-01", 50.097416, 14.462274, 1.0)
filters = admin_db.get_all_date_location_filters()

# Use StravaDataDatabase for data operations
data_db = StravaDataDatabase()
athletes = data_db.get_all_athletes()
activities = data_db.get_activities_filtered("athlete_123", limit=100, activity_type="Run")
```

### Package-Level Imports (Recommended)

```python
# Import from the databases package root
from src.databases import AdminDatabase, StravaDataDatabase

admin_db = AdminDatabase()
data_db = StravaDataDatabase()

# Get activities with filters
activities = data_db.get_activities_filtered("athlete_123", limit=100, activity_type="Run")
```

## Benefits of the New Structure

### 🎯 **Better Organization**
- Database classes are logically grouped in a dedicated folder
- Clear separation between specialized and unified interfaces
- Easier to navigate and understand the codebase

### 🔧 **Improved Maintainability**
- Changes to admin features don't affect data operations
- Changes to data operations don't affect admin features
- Smaller, more focused classes are easier to debug

### 🚀 **Enhanced Testability**
- Each class can be tested independently
- Mock dependencies more easily
- Write focused unit tests for specific functionality

### 📈 **Better Scalability**
- Add new database classes easily (e.g., `AnalyticsDatabase`, `ReportsDatabase`)
- Optimize data operations without affecting admin features
- Easier to extend either part of the system

### 🔄 **Simplified API**
- Clear separation of concerns with specialized classes
- Each database class has a focused purpose
- Easy to understand dependencies between components

## Implementation Guide

### Standard Usage Pattern

```python
from src.databases import AdminDatabase, StravaDataDatabase

# Initialize both database classes
admin_db = AdminDatabase()
data_db = StravaDataDatabase()

# Use them independently based on your needs
athletes = data_db.get_all_athletes()
activities = data_db.get_activities_filtered("athlete_123", limit=100, activity_type="Run")
location_settings = admin_db.get_location_settings()
date_filters = admin_db.get_all_date_location_filters()
```

### Route Setup Pattern

```python
# In main.py
from src.databases import AdminDatabase, StravaDataDatabase
from src.sync_service import ActivitySyncService

admin_db = AdminDatabase()
data_db = StravaDataDatabase()
sync_service = ActivitySyncService(data_db)

# Pass to route setup functions
setup_main_routes(app, data_db, admin_db, sync_service)
setup_admin_routes(app, data_db, admin_db)
```

## Component Responsibilities

### AdminDatabase
Manages all configuration and settings:
- Default location settings (latitude, longitude, radius)
- Date-specific location filters
- Settings management

### StravaDataDatabase
Manages all athlete and activity data:
- Athlete records and sync status
- Activity storage and retrieval
- Activity filtering by type and date

### Separation of Concerns
Each database class operates independently:
- AdminDatabase handles configuration
- StravaDataDatabase handles data operations
- When needed, pass instances between components (e.g., in route handlers)

## Performance Considerations
- Each database class creates independent connections as needed
- Use context managers (`get_connection()`) for automatic connection cleanup
- Database operations are optimized with appropriate indexes
- Activity queries support limits to control result set sizes

## Future Enhancements

### Potential Improvements
1. **Additional Database Classes**: Add specialized classes like `AnalyticsDatabase`, `ReportsDatabase`
2. **Async Support**: Add async versions of database methods
3. **Connection Pooling**: Implement connection pooling for better performance
4. **Query Optimization**: Add query builders and optimization tools
5. **Caching**: Add caching layers for frequently accessed data

### Extension Points
- Admin features can be extended independently (new settings, filters, etc.)
- Data features can be extended independently (new activity types, stats, etc.)
- New specialized database classes can be added to the `databases` folder
- Package structure supports easy addition of new modules