"""
config.py — Central application configuration.
All settings are env-overridable; no hardcoded values in application code.
"""
from pathlib import Path
from typing import Optional
from pydantic import ConfigDict, field_validator
from pydantic_settings import BaseSettings

APP_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "CV Parser API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Security
    SECRET_KEY: str = "dev-key-please-change-in-production"
    ACCESS_TOKEN_EXPIRE_HOURS: int = 24
    CORS_ORIGINS: str = "http://localhost:3000"

    # Storage
    UPLOAD_DIR: Path = Path("uploads")
    LOG_DIR: Path = Path("logs")
    MAX_FILE_SIZE_MB: int = 10
    GOOGLE_SERVICE_ACCOUNT_FILE: Optional[Path] = None
    GOOGLE_SHEETS_SPREADSHEET_ID: Optional[str] = None
    GOOGLE_SHEETS_TAB_NAME: str = "Sheet1"
    GOOGLE_SHEETS_ANALYTICS_TAB_NAME: str = "Batch Analytics"

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/cv_system"

    # Classification thresholds
    MIN_CONFIDENCE_SCORE: float = 0.1

    # Allowed MIME types
    ALLOWED_EXTENSIONS: set = {".pdf", ".docx"}

    # WhatsApp Configuration
    WHATSAPP_API_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_WEBHOOK_VERIFY_TOKEN: str = ""
    WHATSAPP_BUSINESS_ACCOUNT_ID: str = ""
    WHATSAPP_MAX_ATTEMPTS: int = 3
    REDIS_URL: str = "redis://localhost:6379/0"

    @field_validator("DEBUG", mode="before")
    @classmethod
    def normalize_debug(cls, value):
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "prod", "production"}:
                return False
            if normalized in {"debug", "dev", "development"}:
                return True
        return value

    model_config = ConfigDict(
        env_file=APP_DIR / ".env",
        env_file_encoding="utf-8",
    )


settings = Settings()


def _resolve_storage_path(path: Path) -> Path:
    return path if path.is_absolute() else APP_DIR / path


def _resolve_database_url(database_url: str) -> str:
    # For PostgreSQL, no path resolution needed
    return database_url


settings.UPLOAD_DIR = _resolve_storage_path(settings.UPLOAD_DIR)
settings.LOG_DIR = _resolve_storage_path(settings.LOG_DIR)
settings.GOOGLE_SERVICE_ACCOUNT_FILE = (
    _resolve_storage_path(settings.GOOGLE_SERVICE_ACCOUNT_FILE)
    if settings.GOOGLE_SERVICE_ACCOUNT_FILE
    else None
)
settings.DATABASE_URL = _resolve_database_url(settings.DATABASE_URL)

# Ensure directories exist on import
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.LOG_DIR.mkdir(parents=True, exist_ok=True)
