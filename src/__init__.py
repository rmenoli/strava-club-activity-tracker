# Export main database classes for backward compatibility
from .database import StravaDatabase
from .databases.admin_database import AdminDatabase
from .databases.strava_data_database import StravaDataDatabase
from .databases.unified_database import StravaDatabase as UnifiedDatabase

__all__ = ["StravaDatabase", "AdminDatabase", "StravaDataDatabase", "UnifiedDatabase"]
