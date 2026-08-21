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

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()

# Chemins fixes côté conteneur, imposés par les cibles de bind mount de
# docker-compose.yml (volumes de app). Volontairement PAS des champs
# Settings : HOST_LIBRARY_ROOT et SHARES_MOUNT sont aussi des noms de
# variables d'environnement hôte (utilisées par docker-compose.yml pour
# l'interpolation ${...} et par install.sh), et pydantic-settings est
# case-insensitive — un champ Settings du même nom serait écrasé par la
# valeur hôte injectée dans l'environnement du conteneur. Ces chemins ne
# doivent jamais être pilotables par une variable d'environnement.
HOST_LIBRARY_ROOT = "/library-root"
SHARES_MOUNT = "/library-root/shares"
