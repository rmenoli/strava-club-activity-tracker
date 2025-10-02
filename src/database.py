# Import the new unified database class for backward compatibility
from .unified_database import StravaDatabase

# Re-export for backward compatibility
__all__ = ["StravaDatabase"]
