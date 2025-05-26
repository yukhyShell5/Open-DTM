from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List # Ensure List is imported
import uuid

class TargetInfo(BaseModel):
    url: Optional[str] = None
    service_type: Optional[str] = None
    additional_params: Dict[str, Any] = Field(default_factory=dict)

class ChunkStrategy(BaseModel):
    type: str = Field("LINE_BASED", description="Currently only LINE_BASED is supported")
    size: int = Field(10000, description="Number of lines per chunk")

class JobCreateRequest(BaseModel):
    target_info: TargetInfo = Field(..., description="Information about the target")
    wordlist_storage_type: str = Field("minio", description="Storage type: 'minio', 's3', 'nfs'")
    wordlist_path: str = Field(..., description="Full path/URI to the wordlist in storage (e.g., bucket_name/file.txt for MinIO/S3)")
    chunk_strategy: ChunkStrategy = Field(default_factory=ChunkStrategy)
    job_priority: int = Field(0, description="Job priority (higher means more important, future use)")

class JobCreateResponse(BaseModel):
    job_id: str
    message: str
    detail_url: Optional[str] = None

class JobDefinition(BaseModel):
    job_id: str
    target_info_json_str: str
    wordlist_path: str
    wordlist_storage_type: str
    status: str # Specific values managed by application logic
    total_chunks: Optional[int] = None
    chunk_definition_type: str
    chunk_size: int
    submitted_at: float
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    job_priority: int

class JobStats(BaseModel):
    status: str # Specific values managed by application logic
    chunks_processed: int = 0
    results_found: int = 0
    chunks_failed: int = 0

# New models for this subtask:
class JobStatusResponse(BaseModel):
    job_definition: JobDefinition
    job_stats: JobStats
    estimated_completion_percentage: Optional[float] = None

class JobResultItem(BaseModel): 
    word: str
    chunk_id: str
    job_id: str
    worker_id: str
    timestamp: float

class JobResultsResponse(BaseModel):
    job_id: str
    results: List[JobResultItem] 
    total_results_in_queue: int 
    fetched_count: int
    offset: int
    limit: int

class JobControlResponse(BaseModel):
    job_id: str
    status: str
    message: str
