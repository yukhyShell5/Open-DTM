from pydantic_settings import BaseSettings
import uuid
from typing import Optional # Add this

class WorkerSettings(BaseSettings):
    WORKER_ID: str = str(uuid.uuid4())
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_USE_SSL: bool = False
    TASK_POLL_TIMEOUT: int = 5 # Timeout for BRPOP
    TARGET_JOB_ID: Optional[str] = None # Worker will listen to queue:tasks:<TARGET_JOB_ID>

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'

worker_settings = WorkerSettings()
