import os

APP_ENVIRONMENT: str = os.getenv("APP_ENVIRONMENT") or "STAGING"
APP_URL: str = os.getenv("APP_URL") or "127.0.0.1"
APP_PORT: int = int(os.getenv("APP_PORT") or 8000)
APP_LOG_LEVEL: str = os.getenv("APP_LOG_LEVEL") or "info"
APP_TIMEOUT: int = int(os.getenv("APP_TIMEOUT") or 600)

TMDB_API_KEY: str | None = os.getenv("TMDB_API_KEY")

TRAKT_CLIENT_ID: str | None = os.getenv("TRAKT_CLIENT_ID")
TRAKT_CLIENT_SECRET: str | None = os.getenv("TRAKT_CLIENT_SECRET")

FIREBASE_PROD_KEY: str | None = os.getenv("FIREBASE_PROD_KEY")
FIREBASE_STAGING_KEY: str | None = os.getenv("FIREBASE_STAGING_KEY")

SPONSOR: str = os.getenv("SPONSOR") or ""