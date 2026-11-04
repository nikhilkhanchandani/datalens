"""Application configuration.

Uses pydantic-settings so config values can come from environment variables
(or a .env file) with validated types and sensible defaults, instead of
scattering `os.environ.get(...)` calls through the codebase.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Defaults are anchored to the backend folder, not the current directory, so
# `uvicorn` started from elsewhere still uses the same database and uploads.
BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = BACKEND_DIR / "data"


class Settings(BaseSettings):
    app_name: str = "DataLens API"
    # "production" turns off the interactive API docs; everything else keeps them on.
    environment: str = "development"

    # Comma-separated list is simplest to express in a .env file; the
    # frontend's own .env.example documents the matching API base URL.
    cors_origins: list[str] = ["http://localhost:3000"]

    # SQLite holds dataset *metadata* only; the uploaded CSVs themselves are
    # streamed to disk under upload_dir, named by generated UUID rather than
    # the user-supplied filename.
    database_url: str = f"sqlite:///{(DEFAULT_DATA_DIR / 'datalens.db').as_posix()}"
    upload_dir: Path = DEFAULT_DATA_DIR / "uploads"
    max_upload_size_mb: int = 50

    model_config = SettingsConfigDict(env_file=".env", env_prefix="DATALENS_")

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor.

    FastAPI route handlers can depend on this via `Depends(get_settings)`;
    `lru_cache` means the .env file is only read once per process.
    """
    return Settings()
