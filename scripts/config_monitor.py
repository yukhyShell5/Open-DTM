from pydantic_settings import BaseSettings

class MonitorSettings(BaseSettings):
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    STALE_TASK_TIMEOUT_SECONDS: int = 300 # e.g., 5 minutes
    MONITOR_POLL_INTERVAL_SECONDS: int = 60 # How often the monitor checks
    # Potentially a list of job_ids to monitor, or a pattern, or discover active jobs
    # For now, monitor all jobs found via a pattern or a specific list
    JOB_ID_PATTERN: str = "job:*" # Pattern to scan for all job IDs

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'

monitor_settings = MonitorSettings()
