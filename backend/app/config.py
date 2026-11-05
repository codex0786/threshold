from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://localhost/threshold"
    cors_origins: str = "http://localhost:3400"
    environment: str = "development"
    # Public deployment: never write, so nothing a student enters is stored.
    read_only: bool = False
    # Requests per minute per client, per server instance. 0 turns the limit off.
    rate_limit_per_minute: int = 0


settings = Settings()
