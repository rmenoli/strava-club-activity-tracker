"""Unit tests for configuration management."""

import os
import pytest
from unittest.mock import patch, MagicMock

from src.config import Config


class TestConfig:
    """Test suite for Config class."""

    def test_successful_config_with_all_required_vars(self):
        """Test successful config loading with all required environment variables."""
        env_vars = {
            'DATABASE_URL': 'postgresql://test:test@localhost/test_db',
            'STRAVA_CLIENT_ID': 'test_client_id',
            'STRAVA_CLIENT_SECRET': 'test_client_secret',
        }
        with patch.dict(os.environ, env_vars, clear=True):
            with patch('src.config.load_dotenv'):
                config = Config()

                # Verify required fields
                assert config.DATABASE_URL == 'postgresql://test:test@localhost/test_db'
                assert config.STRAVA_CLIENT_ID == 'test_client_id'
                assert config.STRAVA_CLIENT_SECRET == 'test_client_secret'

                # Verify optional fields use defaults
                assert config.STRAVA_REDIRECT_URI == 'http://localhost:8000/auth/strava/callback'
                assert config.SECRET_KEY == 'dev-secret'

    def test_missing_database_url_raises_error(self):
        """Test that missing DATABASE_URL raises ValueError."""
        env_vars = {
            'STRAVA_CLIENT_ID': 'test_client_id',
            'STRAVA_CLIENT_SECRET': 'test_client_secret',
        }
        with patch.dict(os.environ, env_vars, clear=True):
            with patch('src.config.load_dotenv'):
                with pytest.raises(ValueError) as exc_info:
                    Config()

                assert "DATABASE_URL" in str(exc_info.value)

    def test_missing_strava_client_id_raises_error(self):
        """Test that missing STRAVA_CLIENT_ID raises ValueError."""
        env_vars = {
            'DATABASE_URL': 'postgresql://test:test@localhost/test_db',
            'STRAVA_CLIENT_SECRET': 'test_client_secret',
        }
        with patch.dict(os.environ, env_vars, clear=True):
            with patch('src.config.load_dotenv'):
                with pytest.raises(ValueError) as exc_info:
                    Config()

                assert "STRAVA_CLIENT_ID" in str(exc_info.value)

    def test_missing_strava_client_secret_raises_error(self):
        """Test that missing STRAVA_CLIENT_SECRET raises ValueError."""
        env_vars = {
            'DATABASE_URL': 'postgresql://test:test@localhost/test_db',
            'STRAVA_CLIENT_ID': 'test_client_id',
        }
        with patch.dict(os.environ, env_vars, clear=True):
            with patch('src.config.load_dotenv'):
                with pytest.raises(ValueError) as exc_info:
                    Config()

                assert "STRAVA_CLIENT_SECRET" in str(exc_info.value)

    def test_optional_strava_redirect_uri_defaults(self):
        """Test that STRAVA_REDIRECT_URI uses default when not provided."""
        env_vars = {
            'DATABASE_URL': 'postgresql://test:test@localhost/test_db',
            'STRAVA_CLIENT_ID': 'test_client_id',
            'STRAVA_CLIENT_SECRET': 'test_client_secret',
        }
        with patch.dict(os.environ, env_vars, clear=True):
            with patch('src.config.load_dotenv'):
                config = Config()

                assert config.STRAVA_REDIRECT_URI == 'http://localhost:8000/auth/strava/callback'

    def test_optional_strava_redirect_uri_custom_value(self):
        """Test that STRAVA_REDIRECT_URI can be overridden."""
        env_vars = {
            'DATABASE_URL': 'postgresql://test:test@localhost/test_db',
            'STRAVA_CLIENT_ID': 'test_client_id',
            'STRAVA_CLIENT_SECRET': 'test_client_secret',
            'STRAVA_REDIRECT_URI': 'https://example.com/callback',
        }
        with patch.dict(os.environ, env_vars, clear=True):
            with patch('src.config.load_dotenv'):
                config = Config()

                assert config.STRAVA_REDIRECT_URI == 'https://example.com/callback'

    def test_optional_secret_key_defaults(self):
        """Test that SECRET_KEY uses default when not provided."""
        env_vars = {
            'DATABASE_URL': 'postgresql://test:test@localhost/test_db',
            'STRAVA_CLIENT_ID': 'test_client_id',
            'STRAVA_CLIENT_SECRET': 'test_client_secret',
        }
        with patch.dict(os.environ, env_vars, clear=True):
            with patch('src.config.load_dotenv'):
                config = Config()

                assert config.SECRET_KEY == 'dev-secret'

    def test_optional_secret_key_custom_value(self):
        """Test that SECRET_KEY can be overridden."""
        env_vars = {
            'DATABASE_URL': 'postgresql://test:test@localhost/test_db',
            'STRAVA_CLIENT_ID': 'test_client_id',
            'STRAVA_CLIENT_SECRET': 'test_client_secret',
            'SECRET_KEY': 'custom-secret-key-12345',
        }
        with patch.dict(os.environ, env_vars, clear=True):
            with patch('src.config.load_dotenv'):
                config = Config()

                assert config.SECRET_KEY == 'custom-secret-key-12345'

    def test_empty_string_values_treated_as_missing(self):
        """Test that empty string values for required fields raise ValueError."""
        env_vars = {
            'DATABASE_URL': '',  # Empty string
            'STRAVA_CLIENT_ID': 'test_client_id',
            'STRAVA_CLIENT_SECRET': 'test_client_secret',
        }
        with patch.dict(os.environ, env_vars, clear=True):
            with patch('src.config.load_dotenv'):
                with pytest.raises(ValueError) as exc_info:
                    Config()

                assert "DATABASE_URL" in str(exc_info.value)

    def test_all_configuration_fields_present(self):
        """Test that all expected configuration fields are present."""
        env_vars = {
            'DATABASE_URL': 'postgresql://test:test@localhost/test_db',
            'STRAVA_CLIENT_ID': 'test_client_id',
            'STRAVA_CLIENT_SECRET': 'test_client_secret',
            'STRAVA_REDIRECT_URI': 'https://example.com/callback',
            'SECRET_KEY': 'my-secret-key',
        }
        with patch.dict(os.environ, env_vars, clear=True):
            with patch('src.config.load_dotenv'):
                config = Config()

                # Verify all expected attributes exist
                assert hasattr(config, 'DATABASE_URL')
                assert hasattr(config, 'STRAVA_CLIENT_ID')
                assert hasattr(config, 'STRAVA_CLIENT_SECRET')
                assert hasattr(config, 'STRAVA_REDIRECT_URI')
                assert hasattr(config, 'SECRET_KEY')

                # Verify types
                assert isinstance(config.DATABASE_URL, str)
                assert isinstance(config.STRAVA_CLIENT_ID, str)
                assert isinstance(config.STRAVA_CLIENT_SECRET, str)
                assert isinstance(config.STRAVA_REDIRECT_URI, str)
                assert isinstance(config.SECRET_KEY, str)
