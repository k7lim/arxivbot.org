"""Configuration settings for ArxivBot."""

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Gemini API (default provider)
    gemini_api_key: str = ""

    # Model configuration
    llm_model: str = "gemini/gemini-3-flash-preview"
    embedding_model: str = "gemini/gemini-embedding-001"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"

    # Database
    database_path: Path = Path("./data/arxivbot.db")

    def apply_to_environment(self) -> None:
        """Apply settings to environment variables for litellm."""
        if self.gemini_api_key:
            os.environ["GEMINI_API_KEY"] = self.gemini_api_key


_settings: Settings | None = None


def get_settings() -> Settings:
    """Get application settings (cached)."""
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.apply_to_environment()
    return _settings
