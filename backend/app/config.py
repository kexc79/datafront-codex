from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "DataFront"
    app_env: str = "development"
    app_secret_key: str = Field(default="change-me", min_length=8)
    access_token_expire_minutes: int = 720

    database_url: str = "sqlite:///./datafront.db"

    initial_admin_email: str = "admin@datafront.local"
    initial_admin_password: str = "change-me-admin-password"
    initial_admin_name: str = "DataFront Admin"

    oracle_dsn: str = "oracle-host:1521/service"
    oracle_user: str = "oracle_user"
    oracle_password: str = ""
    oracle_instant_client_dir: str = "/opt/oracle/instantclient"
    oracle_enable_thick_mode: bool = True

    upload_root: str = "/var/lib/datafront/uploads"
    max_upload_mb: int = 512
    allowed_upload_extensions: str = "xlsx,xls,csv,txt,zip,rar,7z"

    ag_grid_license_key: str = ""

    @property
    def upload_path(self) -> Path:
        return Path(self.upload_root)

    @property
    def allowed_extensions(self) -> set[str]:
        return {item.strip().lower().lstrip(".") for item in self.allowed_upload_extensions.split(",") if item.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
