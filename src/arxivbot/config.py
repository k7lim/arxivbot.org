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
    gemini_api_key_paid: str | None = None

    # Model configuration
    llm_model: str = "gemini/gemini-3.8-flash"
    # Tried in order on the free key when the primary fails or is rate limited.
    # Each model has its own free-tier quota (Flash: 5 RPM / 20 RPD each,
    # Flash Lite: 15 RPM / 500 RPD each), so the chain multiplies daily capacity.
    # Comma-separated; set to "" to disable.
    llm_free_fallback_models: str = (
        "gemini/gemini-3.7-flash,gemini/gemini-3.6-flash,gemini/gemini-3.5-flash,"
        "gemini/gemini-3-flash-preview,gemini/gemini-3.5-flash-lite,gemini/gemini-3.1-flash-lite"
    )
    # Used with the paid key (GEMINI_API_KEY_PAID), after the free chain
    llm_fallback_model: str = "gemini/gemini-2.5-flash-lite"

    @property
    def free_fallback_models(self) -> list[str]:
        """Free-tier fallback models in order, without blanks or the primary."""
        models = [m.strip() for m in self.llm_free_fallback_models.split(",")]
        return [m for m in models if m and m != self.llm_model]

    # Public origin used in absolute URLs (robots.txt, sitemap.xml); no trailing slash
    site_url: str = "https://arxivbot.org"

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
