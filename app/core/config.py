from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.enums import DatabaseMode


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # App
    ENV: str = "local"
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60
    DATABASE_MODE: DatabaseMode = DatabaseMode.ORM

    # Logging
    LOG_FILE: str = "logs/app.log"
    LOG_LEVEL: str = "INFO"

    # Database
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # AWS / S3
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "eu-central-1"
    AWS_SESSION_TOKEN: str | None = None
    S3_BUCKET_NAME: str = "projects-dashboard-docs"
    S3_ENDPOINT_URL: str | None = None  # set for local MinIO/moto testing

    # Limits
    MAX_PROJECT_STORAGE_MB: int = 500


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
