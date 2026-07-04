"""
Application settings.

Loads and validates every required credential from `.env.local` at startup
using pydantic-settings. If any required key is missing the app terminates
with a clean, human-readable error instead of failing later at request time.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed view over `.env.local`. Missing fields raise at startup."""

    # --- Gemini ---
    gemini_api_key: str = Field(alias="GEMINI_API_KEY")
    gemini_model_name: str = Field(default="gemini-2.0-flash", alias="GEMINI_MODEL_NAME")
    gemini_embedding_model: str = Field(
        default="gemini-embedding-001", alias="GEMINI_EMBEDDING_MODEL"
    )
    gemini_embedding_dimension: int = Field(default=768, alias="GEMINI_EMBEDDING_DIMENSION")

    # --- Pinecone ---
    pinecone_api_key: str = Field(alias="PINECONE_API_KEY")
    pinecone_index_name: str = Field(default="life-coach-index", alias="PINECONE_INDEX_NAME")

    # --- Firebase ---
    firebase_service_account_path: str = Field(alias="FIREBASE_SERVICE_ACCOUNT_PATH")

    # --- Google Calendar OAuth ---
    google_oauth_client_id: str = Field(alias="GOOGLE_OAUTH_CLIENT_ID")
    google_oauth_client_secret: str = Field(alias="GOOGLE_OAUTH_CLIENT_SECRET")
    google_oauth_redirect_uri: str = Field(alias="GOOGLE_OAUTH_REDIRECT_URI")

    # --- App ---
    app_env: str = Field(default="local", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # --- Daily recommendation push (FCM) ---
    daily_push_enabled: bool = Field(default=True, alias="DAILY_PUSH_ENABLED")
    daily_push_hour_ist: int = Field(
        default=7, ge=0, le=23, alias="DAILY_PUSH_HOUR_IST",
        description="Hour of day (Asia/Kolkata) to send the daily push.",
    )

    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def validate_service_account_file(self) -> None:
        """Fail fast if the Firebase service-account JSON does not exist on disk."""
        if not Path(self.firebase_service_account_path).is_file():
            raise FileNotFoundError(
                f"Firebase service account file not found at "
                f"'{self.firebase_service_account_path}'. "
                "Check FIREBASE_SERVICE_ACCOUNT_PATH in .env.local."
            )


@lru_cache
def get_settings() -> Settings:
    """
    Return the singleton Settings instance.

    Cached so the .env.local file is parsed exactly once per process.
    Raises pydantic.ValidationError listing every missing key if the
    environment is incomplete.
    """
    return Settings()
