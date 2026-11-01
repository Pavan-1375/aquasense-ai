from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    secret_key: str = "development-only-change-me"
    database_url: str = "sqlite:///./backend/hydroinsight.db"
    app_base_url: str = "http://127.0.0.1:5173"
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    device_ingest_key: str = "local-device-key"
    seed_demo: bool = False
    scheduler_enabled: bool = True
    scheduler_interval_seconds: int = 60
    email_provider: str = "development"
    email_from: str = "AquaSense AI <no-reply@example.local>"
    sms_provider: str = "development"
    sms_from: str = "AquaSense AI"
    upload_dir: str = "backend/uploads"
    max_upload_mb: int = 10
    stale_measurement_hours: int = 24
    rate_limit_enabled: bool = True
    rate_limit_window_seconds: int = 60
    rate_limit_auth_requests: int = 12
    rate_limit_ingest_requests: int = 600
    schema_auto_create: bool = True

    model_config = SettingsConfigDict(env_file=(".env", "backend/.env"), extra="ignore")

    def validate_production_secrets(self) -> None:
        if self.app_env.lower() == "production" and (self.secret_key == "development-only-change-me" or self.device_ingest_key == "local-device-key"):
            raise RuntimeError("Production requires non-default SECRET_KEY and DEVICE_INGEST_KEY")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_production_secrets()
    return settings

