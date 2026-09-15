import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    REDIS_URL: str = "redis://localhost:6379/0"
    DATABASE_PATH: str = "./signalmap.db"

    GROQ_API_KEY: str = ""
    GROQ_TEXT_MODEL: str = "llama-3.3-70b-versatile"

    YOUTUBE_API_KEY: str = ""
    REDDIT_CLIENT_ID: str = ""
    REDDIT_CLIENT_SECRET: str = ""
    REDDIT_USER_AGENT: str = "SignalMapAI/1.0"
    GITHUB_TOKEN: str = ""

    @property
    def get_database_path(self) -> str:
        """Returns /tmp/signalmap.db in Vercel / Lambda environment, otherwise DATABASE_PATH."""
        if os.getenv("VERCEL") or os.getenv("VERCEL_ENV") or os.getenv("AWS_LAMBDA_FUNCTION_NAME") or os.getenv("NOW_REGION"):
            return "/tmp/signalmap.db"
        return self.DATABASE_PATH

    @property
    def is_vercel(self) -> bool:
        """Returns True if running inside Vercel serverless functions."""
        return bool(os.getenv("VERCEL") or os.getenv("VERCEL_ENV") or os.getenv("AWS_LAMBDA_FUNCTION_NAME") or os.getenv("NOW_REGION"))

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
