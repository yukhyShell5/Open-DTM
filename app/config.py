from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "Distributed Brute-Force API"
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_USE_SSL: bool = False

    class Config:
        env_file = ".env" # For local development to override
        env_file_encoding = 'utf-8'

settings = Settings()
