from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, model_validator
import json


class Settings(BaseSettings):
    # Reads from .env in cwd, then falls back to ../.env (project root)
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Individual DB vars — docker-compose uses these to spin up postgres
    DB_USER: str = "annotaterl"
    DB_PASSWORD: str = "annotaterl"
    DB_NAME: str = "annotaterl"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5433

    # Assembled at validation time if not explicitly set
    DATABASE_URL: str = ""

    REDIS_URL: str
    SECRET_KEY: str

    @model_validator(mode="after")
    def assemble_db_url(self) -> "Settings":
        if not self.DATABASE_URL:
            self.DATABASE_URL = (
                f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
                f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            )
        return self

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    ANTHROPIC_API_KEY: str | None = None

    S3_BUCKET: str
    S3_ENDPOINT_URL: str | None = None
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    S3_REGION: str = "us-east-1"

    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v: str | list) -> list[str]:
        if isinstance(v, str):
            return json.loads(v)
        return v


settings = Settings()
