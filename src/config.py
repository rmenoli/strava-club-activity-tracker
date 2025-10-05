"""Centralized configuration management with validation."""

import os
import sys

from dotenv import load_dotenv


class Config:
    """Application configuration loaded from environment variables.

    All configuration values are loaded at startup and validated.
    Missing required variables will cause the application to exit immediately.
    """

    def __init__(self):
        """Initialize configuration from environment variables."""
        # Load .env file
        load_dotenv()

        # Required configuration
        self.DATABASE_URL: str = self._get_required("DATABASE_URL")
        self.STRAVA_CLIENT_ID: str = self._get_required("STRAVA_CLIENT_ID")
        self.STRAVA_CLIENT_SECRET: str = self._get_required("STRAVA_CLIENT_SECRET")

        # Optional configuration with defaults
        self.STRAVA_REDIRECT_URI: str = os.getenv(
            "STRAVA_REDIRECT_URI", "http://localhost:8000/auth/strava/callback"
        )
        self.SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret")

    def _get_required(self, key: str) -> str:
        """Get a required environment variable.

        Args:
            key: Environment variable name

        Returns:
            The environment variable value

        Raises:
            ValueError: If the environment variable is not set
        """
        value = os.getenv(key)
        if not value:
            raise ValueError(f"Required environment variable '{key}' is not set")
        return value


def load_config() -> Config:
    """Load and validate configuration from environment variables.

    Returns:
        Config: Validated configuration instance

    Exits:
        Exits the application with error message if validation fails
    """
    try:
        config = Config()
        return config
    except ValueError as e:
        print("=" * 60)
        print("ERROR: Configuration validation failed")
        print("=" * 60)
        print(f"\n{str(e)}\n")
        print("Please ensure all required environment variables are set:")
        print("  - DATABASE_URL (required)")
        print("  - STRAVA_CLIENT_ID (required)")
        print("  - STRAVA_CLIENT_SECRET (required)")
        print(
            "  - STRAVA_REDIRECT_URI (optional, defaults to http://localhost:8000/auth/strava/callback)"
        )
        print("  - SECRET_KEY (optional, defaults to 'dev-secret')")
        print("\nCopy .env-example to .env and fill in the values.")
        print("=" * 60)
        sys.exit(1)
