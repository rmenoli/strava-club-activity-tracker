"""Authentication and authorization helpers."""

from typing import Optional

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.config import Config


def is_admin(athlete_id: Optional[str], config: Config) -> bool:
    """Check if an athlete ID is in the admin whitelist.

    Args:
        athlete_id: The Strava athlete ID to check (can be None)
        config: Application configuration containing admin whitelist

    Returns:
        True if the athlete is an admin, False otherwise
    """
    if not athlete_id:
        return False
    return athlete_id in config.ADMIN_ATHLETE_IDS


def require_admin(request: Request, config: Config) -> Optional[HTMLResponse]:
    """Check if the current user is an admin.

    This function should be called at the beginning of admin routes.
    It handles both authentication (is user logged in?) and authorization
    (is user an admin?).

    Args:
        request: FastAPI request object with session data
        config: Application configuration containing admin whitelist

    Returns:
        None if user is authorized (admin can proceed)
        RedirectResponse to /login if user is not logged in
        HTMLResponse with 403 error if user is logged in but not an admin

    Example:
        @app.get("/admin")
        async def admin_dashboard(request: Request):
            if auth_response := require_admin(request, config):
                return auth_response
            # Admin-only code here
    """
    athlete_id = request.session.get("athlete_id")

    # Not logged in - redirect to login
    if not athlete_id:
        return RedirectResponse("/login")

    # Logged in but not an admin - show 403
    if not is_admin(athlete_id, config):
        return HTMLResponse(
            """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Access Denied</title>
                <style>
                    body {
                        font-family: Arial, sans-serif;
                        max-width: 600px;
                        margin: 100px auto;
                        padding: 20px;
                        text-align: center;
                    }
                    h1 { color: #d32f2f; }
                    a {
                        color: #fc4c02;
                        text-decoration: none;
                        font-weight: bold;
                    }
                    a:hover { text-decoration: underline; }
                </style>
            </head>
            <body>
                <h1>⛔ Access Denied</h1>
                <p>You do not have permission to access this page.</p>
                <p>Admin access is restricted to authorized users only.</p>
                <p><a href="/">← Back to Dashboard</a></p>
            </body>
            </html>
            """,
            status_code=403,
        )

    # User is an admin - allow access
    return None
