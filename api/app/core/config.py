from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_ENV: str = "development"
    DEBUG: bool = True

    # MongoDB
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "onenine"

    # Golf Course API
    GOLF_API_KEY: str = ""
    GOLF_API_BASE: str = "https://api.golfcourseapi.com/v1"

    # Overpass API endpoints (OSM)
    OVERPASS_ENDPOINTS: list[str] = [
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass-api.de/api/interpreter",
    ]

    # Frontend
    FRONTEND_URL: str = "http://agentcll.local:6969"

    # Cache TTLs (seconds)
    SEARCH_CACHE_TTL: int = 60 * 60 * 24 * 7  # 7 days
    MAP_CACHE_TTL: int = 60 * 60 * 24 * 30  # 30 days

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
