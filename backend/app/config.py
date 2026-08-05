from pathlib import Path

from pydantic import field_validator
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

    # AI analyst (OpenAI-compatible endpoint; OpenRouter by default)
    ai_base_url: str = "https://openrouter.ai/api/v1"
    ai_api_key: str = ""
    ai_model: str = "meta-llama/llama-3.3-70b-instruct"
    ai_vision_model: str = "google/gemini-2.0-flash-001"

    sync_lookback_days: int = 7
    catchup_after_hours: int = 12

    @field_validator(
        "data_source", "tz", "garmin_email", "garmin_password",
        "usda_api_key", "ai_base_url", "ai_api_key", "ai_model",
        "ai_vision_model",
        mode="before",
    )
    @classmethod
    def _strip(cls, v: object) -> object:
        return v.strip() if isinstance(v, str) else v


settings = Settings()
