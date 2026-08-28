from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class EnvSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")
    app_config_path: str = "../config/app.yaml"
    database_url: str = "sqlite:///./impossible_pov.db"
    cors_origins: str = "http://localhost:3000"
    openai_api_key: str | None = None
    runway_api_key: str | None = None
    elevenlabs_api_key: str | None = None
    azure_speech_key: str = ""
    azure_speech_region: str = "eastus"
    youtube_client_id: str | None = None
    youtube_client_secret: str | None = None
    youtube_refresh_token: str | None = None


class AppConfig(BaseModel):
    raw: dict[str, Any]

    def get(self, path: str, default: Any = None) -> Any:
        current: Any = self.raw
        for key in path.split("."):
            if not isinstance(current, dict) or key not in current:
                return default
            current = current[key]
        return current


@lru_cache
def get_env() -> EnvSettings:
    return EnvSettings()


@lru_cache
def get_config() -> AppConfig:
    env = get_env()
    path = Path(env.app_config_path)
    if not path.is_absolute():
        path = (Path(__file__).resolve().parents[2] / path).resolve()
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return AppConfig(raw=data)
