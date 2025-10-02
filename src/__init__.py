# Export main database classes for backward compatibility
from .admin_database import AdminDatabase
from .database import StravaDatabase
from .strava_data_database import StravaDataDatabase
from .unified_database import StravaDatabase as UnifiedDatabase

__all__ = ["StravaDatabase", "AdminDatabase", "StravaDataDatabase", "UnifiedDatabase"]
