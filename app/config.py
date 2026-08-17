from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ntfy_url: str
    ntfy_topic: str
    sonarr_secret: str
    radarr_secret: str
    lidarr_secret: str
    readarr_secret: str
    sonarr_url: str
    sonarr_api_key: str
    radarr_url: str
    radarr_api_key: str
    lidarr_url: str
    lidarr_api_key: str
    readarr_url: str
    readarr_api_key: str
    jellyfin_url: str
    jellyfin_api_key: str
    jellyfin_public_url: str
    session_secret: str
    cache_ttl: int = 30
    db_path: str = "data/cache.db"
    calibre_library_path: str = "data/calibre-library"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
