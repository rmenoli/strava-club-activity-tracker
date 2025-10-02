# Database Refactoring Documentation

## Overview

The `StravaDatabase` class has been refactored into a modular architecture with specialized database classes organized in a dedicated `databases` folder:

1. **`AdminDatabase`** - Handles admin-related operations (settings, date filters)
2. **`StravaDataDatabase`** - Handles core data operations (athletes, activities, GPS filtering)
3. **`StravaDatabase`** (Unified) - Maintains backward compatibility by delegating to the specialized classes

## New File Structure

```
src/
├── __init__.py              # Package exports
├── database.py              # Backward-compatible import (imports from databases/unified_database)
├── databases/               # 🆕 NEW: Dedicated databases folder
│   ├── __init__.py          # Database package exports
│   ├── admin_database.py    # AdminDatabase class
│   ├── strava_data_database.py  # StravaDataDatabase class
│   └── unified_database.py  # Unified StravaDatabase class
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

### 3. Unified StravaDatabase (`src/databases/unified_database.py`)

**Purpose**: Provides a unified interface that maintains backward compatibility while delegating operations to specialized classes.

**Key Features**:
- Delegates admin operations to `AdminDatabase`
- Delegates data operations to `StravaDataDatabase`
- Maintains the same public API as the original monolithic class
- Handles cross-class dependencies (e.g., GPS filtering needs admin settings)

## Usage Examples

### Direct Usage of Specialized Classes (Recommended for new code)

```python
# Import from the databases package
from src.databases.admin_database import AdminDatabase
from src.databases.strava_data_database import StravaDataDatabase

# Use AdminDatabase directly for admin operations
admin_db = AdminDatabase()
admin_db.set_setting("target_latitude", "50.097416")
filters = admin_db.get_all_date_location_filters()

# Use StravaDataDatabase directly for data operations
data_db = StravaDataDatabase()
athletes = data_db.get_all_athletes()
activities = data_db.get_activities_filtered("athlete_123", admin_db)
```

### Package-level imports

```python
# Import from the databases package root
from src.databases import AdminDatabase, StravaDataDatabase

admin_db = AdminDatabase()
data_db = StravaDataDatabase()
```

### Unified Usage (Backward Compatible)

```python
# Continue using the unified interface - works exactly as before
from src.database import StravaDatabase
db = StravaDatabase()

# All existing methods work exactly the same
db.set_setting("target_latitude", "50.097416")
athletes = db.get_all_athletes()
activities = db.get_activities_filtered("athlete_123")
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

### 🔄 **Full Backward Compatibility**
- Existing code continues to work unchanged
- Gradual migration path for future improvements
- No breaking changes to the public API

## Migration Guide

### For New Development
- Use specialized classes directly: `from src.databases import AdminDatabase, StravaDataDatabase`
- Use the unified class when you need both or want the simplest interface

### For Existing Code
- **No changes required** - all existing code continues to work
- `from src.database import StravaDatabase` still works exactly as before
- Optionally migrate to direct usage of specialized classes for better performance and clarity

### Example Migration

```python
# Before (still works)
from src.database import StravaDatabase
db = StravaDatabase()
activities = db.get_activities_filtered("athlete_123")

# After (recommended for new code)
from src.databases import AdminDatabase, StravaDataDatabase
admin_db = AdminDatabase()
data_db = StravaDataDatabase()
activities = data_db.get_activities_filtered("athlete_123", admin_db)
```

## Cross-Class Dependencies

### GPS Filtering
GPS filtering requires both data and admin components:
- `StravaDataDatabase.filter_activities()` needs admin settings for location data
- The unified class handles this automatically
- Direct usage requires manually passing the admin database instance

### Example:
```python
# Direct usage - manual dependency management
admin_db = AdminDatabase()
data_db = StravaDataDatabase()
activities = data_db.get_activities_filtered("athlete_123", admin_db)

# Unified usage - automatic dependency management
db = StravaDatabase()
activities = db.get_activities_filtered("athlete_123")  # admin_db handled internally
```

## Performance Considerations
- Direct usage of specialized classes has slightly better performance (no delegation overhead)
- Unified class has minimal overhead and maintains full functionality
- Database connection overhead is the same regardless of approach

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