from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_source: str = "mock"  # "mock" | "garmin"
    tz: str = "Europe/Dublin"
    db_path: Path = BACKEND_DIR / "data" / "health.db"

    garmin_email: str = ""
    garmin_password: str = ""
    garmin_token_dir: Path = BACKEND_DIR / ".garmin_tokens"

    usda_api_key: str = ""

    sync_lookback_days: int = 3
    catchup_after_hours: int = 12


settings = Settings()
