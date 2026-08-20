from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.enums import DatabaseMode


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App (with defaults for serverless/Lambda environments)
    ENV: str = "local"
    SECRET_KEY: str = "lambda-dummy-secret-key"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60
    DATABASE_MODE: DatabaseMode = DatabaseMode.ORM

    # Logging
    LOG_FILE: str = "logs/app.log"
    LOG_LEVEL: str = "INFO"

    # Database (with defaults so Lambda doesn't crash on startup)
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "projects_db"
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
    S3_ENDPOINT_URL: str | None = None

    # Limits
    MAX_PROJECT_STORAGE_MB: int = 500
    MAX_IMAGE_DIMENSION: int = 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
