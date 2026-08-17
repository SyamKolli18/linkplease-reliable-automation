"""Application settings configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/linkplease"
    PSEUDOGRAM_BASE_URL: str = "https://pseudogram-api.onrender.com"
    PSEUDOGRAM_API_BASE_URL: str = ""
    PSEUDOGRAM_API_KEY: str = ""
    WORKER_POLL_INTERVAL: float = 2.0
    MAX_RETRIES: int = 5

    @property
    def pseudogram_url(self) -> str:
        return self.PSEUDOGRAM_API_BASE_URL or self.PSEUDOGRAM_BASE_URL

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
