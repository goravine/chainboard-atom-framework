"""api_app configuration via pydantic-settings.

Pulls config values from environment variables. For runtime values (URLs,
hosts, buckets, secrets) prefer `config/_cfg.json` over env vars — see
PROTOCOL.md "Configuration Protocol."

This file only carries app-level settings like API title and CORS origins.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    API_TITLE: str = "ChainBoardAtom Framework"
    API_VERSION: str = "0.1.0"
    API_DESCRIPTION: str = "Generated from chainboard-atom-framework template"

    ALLOWED_ORIGINS: list[str] = ["*"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
