# Routes package
from .admin_routes import setup_admin_routes
from .main_routes import setup_main_routes

__all__ = ["setup_main_routes", "setup_admin_routes"]
