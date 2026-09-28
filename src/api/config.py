"""
Configuration Manager for Pyro-Harmony.
Safely manages runtime options and masks credentials.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Base paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    DATA_CACHE_DIR: Path = BASE_DIR / "data" / "raw"
    PROCESSED_DIR: Path = BASE_DIR / "data" / "processed"
    MODELS_DIR: Path = BASE_DIR / "models"
    STATIC_DIR: Path = BASE_DIR / "src" / "static"

    # API Keys (Protected - never exposed directly to frontend)
    FIRMS_MAP_KEY: str = ""
    
    # Server settings
    SERVER_HOST: str = "127.0.0.1"
    SERVER_PORT: int = 8000
    DEBUG: bool = False

settings = Settings()

# Ensure directories exist
settings.DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
settings.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
settings.MODELS_DIR.mkdir(parents=True, exist_ok=True)
settings.STATIC_DIR.mkdir(parents=True, exist_ok=True)
