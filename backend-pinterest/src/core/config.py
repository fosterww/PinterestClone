from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Pinterest API"
    debug: bool = False

    db_user: str = "pinterest"
    db_password: str = "pinterest"
    db_name: str = "pinterest"
    db_host: str = "localhost"
    db_port: int = 5432

    @property
    def async_database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql+psycopg2://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    refresh_token_expire_minutes: int = 60 * 24 * 7

    google_client_id: str = ""
    google_client_secret: str = ""

    s3_endpoint_url: str = "http://localhost:9000"
    s3_region: str = "us-east-1"
    s3_access_key_id: str = "minioadmin"
    s3_secret_access_key: str = "minioadmin"
    s3_bucket_name: str = "pinterest"
    s3_public_base_url: str = "http://localhost:9000/pinterest"

    redis_url: str = "redis://localhost:6379/0"
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_socket_timeout: int = 5

    rabbitmq_url: str = "amqp://pinterest:pinterest@localhost:5672//"

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    email_from_address: str = ""
    email_from_name: str = ""
    frontend_base_url: str | None = None

    clarifai_api_key: str
    clarifai_user_id: str
    clarifai_app_id: str

    gemini_api_key: str
    openai_api_key: str

    ai_image_generations_per_day: int = 5
    ai_tag_generations_per_day: int = 30
    ai_description_generations_per_day: int = 10
    ai_image_indexings_per_day: int = 100
    ai_visual_searches_per_day: int = 100
    ai_retries_per_day: int = 10
    ai_openai_image_generation_cost_usd: str = "0.040000"


settings = Settings()
