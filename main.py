import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from src.databases.admin_database import AdminDatabase
from src.databases.strava_data_database import StravaDataDatabase
from src.routes import setup_admin_routes, setup_main_routes
from src.sync_service import ActivitySyncService

load_dotenv()

# Initialize database and sync service
admin_db = AdminDatabase()
data_db = StravaDataDatabase()
sync_service = ActivitySyncService(data_db)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Session middleware (cookie-based session storage)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "dev-secret"),
)

# Setup routes
setup_main_routes(app, data_db, admin_db, sync_service)
setup_admin_routes(app, data_db, admin_db)
