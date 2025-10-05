from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from src.config import load_config
from src.databases.admin_database import AdminDatabase
from src.databases.strava_data_database import StravaDataDatabase
from src.routes import setup_admin_routes, setup_main_routes
from src.sync_service import ActivitySyncService

# Load and validate configuration
config = load_config()

# Initialize database and sync service
admin_db = AdminDatabase(config.DATABASE_URL)
data_db = StravaDataDatabase(config.DATABASE_URL)
sync_service = ActivitySyncService(data_db, config)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Session middleware (cookie-based session storage)
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SECRET_KEY,
)

# Setup routes
setup_main_routes(app, data_db, admin_db, sync_service, config)
setup_admin_routes(app, data_db, admin_db)
