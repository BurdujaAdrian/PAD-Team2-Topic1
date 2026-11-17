# Settings, read from the environment once at startup.

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = 8080

    # Lowest level written to the log: DEBUG, INFO, WARNING or ERROR.
    log_level: str = "INFO"

    # Time between two ETL runs. A run started by POST /run does not move it.
    etl_interval_seconds: float = Field(default=60, gt=0, le=86400)

    # The warehouse every run loads into.
    warehouse_postgres_host: str = "warehouse-db"
    warehouse_postgres_port: int = 5432
    warehouse_postgres_db: str
    warehouse_postgres_user: str
    # SecretStr keeps the passwords out of the startup log.
    warehouse_postgres_password: SecretStr

    # Sources on Postgres.
    base_postgres_host: str = "base-db"
    base_postgres_port: int = 5432
    base_postgres_db: str
    base_postgres_user: str
    base_postgres_password: SecretStr

    crafting_postgres_host: str = "crafting-db"
    crafting_postgres_port: int = 5432
    crafting_postgres_db: str
    crafting_postgres_user: str
    crafting_postgres_password: SecretStr

    zombie_postgres_host: str = "zombie-db"
    zombie_postgres_port: int = 5432
    zombie_postgres_db: str
    zombie_postgres_user: str
    zombie_postgres_password: SecretStr

    resource_postgres_host: str = "resource-db"
    resource_postgres_port: int = 5432
    resource_postgres_db: str
    resource_postgres_user: str
    resource_postgres_password: SecretStr

    # Sources on rqlite, read through its HTTP API.
    game_rqlite_url: str = "http://game-db:4001"
    player_rqlite_url: str = "http://player-db:4001"
    exam_rqlite_url: str = "http://exam-db:4001"
    world_rqlite_url: str = "http://world-db:4001"

    def postgres_dsn(self, name: str) -> str:
        # One builder for the five databases, so a source is named once
        # ("base", "warehouse") instead of passing its five fields around.
        password = getattr(self, f"{name}_postgres_password").get_secret_value()
        return (
            f"host={getattr(self, f'{name}_postgres_host')} "
            f"port={getattr(self, f'{name}_postgres_port')} "
            f"dbname={getattr(self, f'{name}_postgres_db')} "
            f"user={getattr(self, f'{name}_postgres_user')} "
            f"password={password}"
        )


@lru_cache
def settings() -> Settings:
    return Settings()
