from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    zalo_web_url: str = "https://chat.zalo.me/"
    browser_headless: bool = False
    min_send_delay: int = 5
    max_send_delay: int = 10
    max_retry: int = 1
    element_timeout: int = 15
    page_timeout: int = 30
    upload_max_mb: int = 10
    database_url: str = "sqlite:///./zalo_app.db"
    dry_run: bool = False
    dry_run_delay: float = 0.2
    project_root: Path = Field(default=BASE_DIR)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("max_send_delay")
    @classmethod
    def validate_delay_range(cls, value: int, info):
        min_delay = info.data.get("min_send_delay", 5)
        if value < min_delay:
            raise ValueError("MAX_SEND_DELAY must be greater than or equal to MIN_SEND_DELAY")
        return value

    @property
    def upload_dir(self) -> Path:
        return self.project_root / "uploads"

    @property
    def browser_profile_dir(self) -> Path:
        return self.project_root / "browser_profile"

    @property
    def logs_dir(self) -> Path:
        return self.project_root / "logs"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.browser_profile_dir.mkdir(parents=True, exist_ok=True)
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    return settings


settings = get_settings()
