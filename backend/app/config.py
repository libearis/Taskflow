from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://taskflow:taskflow@localhost:5432/taskflow"
    mongo_url: str = "mongodb://localhost:27017"
    mongo_db: str = "taskflow"

    http_port: int = 8000
    grpc_port: int = 50051

    # REST bypasses Envoy entirely (see AGENTS.md #6), so it needs its own
    # CORS handling for the Vite dev server origin.
    cors_origins: list[str] = ["http://localhost:5173"]

    projector_poll_interval_seconds: float = 1.0
    projector_max_retries: int = 5


settings = Settings()
