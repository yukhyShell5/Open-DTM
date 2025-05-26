# Project Structure and Conceptual Snippets

This document outlines a proposed directory structure for the Distributed Brute-Force Framework and provides conceptual Python snippets for key functionalities. These snippets are illustrative and intended to show the core logic and interactions between components, particularly with Redis.

## 1. Proposed Directory Structure

```
bruteforce_framework/
├── app/                      # FastAPI application (API Server)
│   ├── __init__.py
│   ├── main.py               # FastAPI app instance, main router setup
│   ├── api/                  # API endpoint definitions (versioned)
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── jobs.py       # Endpoints related to /jobs (submit, status, pause, resume, results)
│   │       └── models.py     # Pydantic models for API request/response validation
│   ├── core/                 # Core logic for API (e.g., job creation, Redis interactions, chunking initiation)
│   │   ├── __init__.py
│   │   ├── job_manager.py    # Logic for managing job lifecycle, interacting with Redis for job data
│   │   └── wordlist_processor.py # Logic for wordlist metadata fetching and chunk calculation
│   ├── utils/                # Utility functions specific to the API server
│   │   └── __init__.py
│   └── config.py             # API server configuration loading (e.g., from environment variables)
├── workers/                  # Worker node logic
│   ├── __init__.py
│   ├── worker.py             # Main worker script, including the processing loop
│   ├── target_connectors/    # Placeholder for different target interaction logic modules
│   │   ├── __init__.py       # (e.g., hash_cracker.py, web_login_attacker.py)
│   │   └── hash_cracker.py   # Example connector for hash cracking
│   └── config.py             # Worker configuration loading
├── common/                   # Code shared between API Server and Worker nodes
│   ├── __init__.py
│   ├── redis_client.py       # Standardized Redis connection setup
│   ├── storage_clients.py    # Clients for accessing external storage (S3, MinIO, NFS abstraction)
│   └── models.py             # Common Pydantic models (e.g., TaskMessage, ChunkDefinition) if any
├── docs/                     # Design documents (like this one and others previously created)
│   ├── architecture.md
│   ├── redis_structures.md
│   ├── wordlist_management.md
│   ├── worker_logic.md
│   ├── fault_tolerance.md
│   ├── api_design.md
│   └── project_structure_and_snippets.md # This file
├── tests/                    # Unit and integration tests for all components
│   ├── app/                  # Tests for the API server
│   ├── workers/              # Tests for the worker logic
│   └── common/               # Tests for shared code
├── scripts/                  # Utility scripts (e.g., manual job submission, monitor process, cleanup tools)
│   └── monitor.py            # Standalone stale task monitor script (as described in fault_tolerance.md)
├── .env.example              # Example environment variables for API and workers
├── requirements.txt          # Python dependencies for the project
└── README.md                 # Project README with setup, usage instructions, etc.
```

### Explanation of Main Directories:

*   **`app/`**: Contains all code related to the FastAPI-based API server. This includes endpoint definitions (`api/`), core business logic (`core/`), utility functions (`utils/`), and configuration (`config.py`).
*   **`workers/`**: Houses the logic for the worker nodes. This includes the main worker script (`worker.py`), specific modules for interacting with different types of targets (`target_connectors/`), and worker configuration.
*   **`common/`**: Holds code shared between the API server and worker nodes, such as Redis client setup and clients for accessing wordlist storage. This promotes DRY (Don't Repeat Yourself) principles.
*   **`docs/`**: Stores all design and architecture documentation for the project.
*   **`tests/`**: Contains all automated tests, organized by the component they are testing.
*   **`scripts/`**: Provides a place for operational or utility scripts, such as a standalone monitor for handling stale tasks.

## 2. Python Snippets (Conceptual)

**Note:** These snippets are illustrative to demonstrate core logic and interactions. They are not fully runnable as they omit full error handling, configuration loading, precise Redis/storage client initialization, and complete Pydantic models.

### A. Worker: Task Fetching and Processing Loop (in `workers/worker.py`)

```python
import redis
import time
import json
from typing import Dict, Any, List

# --- Assume these are properly initialized elsewhere based on config ---
# from common.redis_client import get_redis_connection
# from common.storage_clients import get_storage_client, BaseStorageClient
# from .config import WORKER_CONFIG, REDIS_SETTINGS

# r: redis.Redis = get_redis_connection(**REDIS_SETTINGS)
# storage_client: BaseStorageClient = get_storage_client(
#     storage_type=WORKER_CONFIG.WORDLIST_STORAGE_TYPE,
#     config=WORKER_CONFIG.STORAGE_CONFIG
# )
# --- End Initialization Placeholder ---

# Placeholder for actual brute-force logic specific to target type
# This would likely be dynamically loaded from 'target_connectors' based on job_details
def perform_attempt_on_target(word: str, target_info: Dict[str, Any]) -> bool:
    """
    Performs a single brute-force attempt against the target.
    This function would encapsulate the logic for hashing, making web requests, etc.
    """
    # Example: for a hash cracking job
    # if target_info.get("type") == "hash":
    #     hashed_word = hashlib.sha256(word.encode()).hexdigest() # Simplified
    #     return hashed_word == target_info.get("hash_value")
    print(f"Worker {WORKER_CONFIG.ID}: Attempting word '{word}' against target: {target_info.get('identifier', 'N/A')}")
    time.sleep(0.001) # Simulate work for one attempt
    # Example success condition for demonstration
    if word == "secret_password":
        return True
    return False # Default to failure

def process_chunk_words(job_id: str, chunk_id: str, words: List[str], job_details: Dict[str, Any], r_conn: redis.Redis):
    """Processes words from a fetched chunk."""
    target_info = job_details.get("target_info", {}) # Should be deserialized if stored as JSON string
    
    found_flag = False
    for word in words:
        if perform_attempt_on_target(word, target_info):
            result_payload = json.dumps({
                "word": word, 
                "chunk_id": chunk_id, 
                "worker_id": WORKER_CONFIG.ID,
                "timestamp": time.time()
            })
            r_conn.lpush(f"list:results:{job_id}", result_payload)
            r_conn.hincrby(f"job_stats:{job_id}", "results_found", 1)
            print(f"Worker {WORKER_CONFIG.ID}: Found result for job {job_id} in chunk {chunk_id}!")
            found_flag = True
            # Depending on job settings (e.g., find_first), worker might stop or continue
            # For simplicity, let's assume it continues for now.
    return found_flag

def worker_main_loop(r_conn: redis.Redis, storage: Any): # storage: BaseStorageClient
    """Main loop for the worker to fetch and process tasks."""
    print(f"Worker {WORKER_CONFIG.ID} starting...")
    # Workers might listen to multiple job queues or a general queue system.
    # For simplicity, this example implies a worker might be assigned or pick jobs.
    # A more robust system might have a list of active job_ids to poll.
    
    # Example: Listen to a specific job's queue (can be adapted for multiple jobs)
    # This is a placeholder; a real worker might get job_id from a different queue or config
    example_job_id_to_monitor = "some_active_job_id" # This would be dynamically determined
    task_queue_key = f"queue:tasks:{example_job_id_to_monitor}"

    while True:
        try:
            # Check job status (e.g., PAUSED, CANCELLED) before blocking on task queue
            job_operational_status_raw = r_conn.hget(f"job_stats:{example_job_id_to_monitor}", "status")
            job_operational_status = job_operational_status_raw.decode() if job_operational_status_raw else "UNKNOWN"

            if job_operational_status == "PAUSED":
                print(f"Worker {WORKER_CONFIG.ID}: Job {example_job_id_to_monitor} is PAUSED. Sleeping.")
                time.sleep(WORKER_CONFIG.PAUSE_POLL_INTERVAL_SECONDS)
                continue
            if job_operational_status in ["CANCELLED", "COMPLETED_SUCCESS", "COMPLETED_NOTFOUND", "FAILED"]:
                print(f"Worker {WORKER_CONFIG.ID}: Job {example_job_id_to_monitor} is in terminal state '{job_operational_status}'. Not fetching tasks.")
                time.sleep(WORKER_CONFIG.TERMINAL_STATE_POLL_INTERVAL_SECONDS) # Or switch to another job
                continue

            # Blocking pop from the task queue for the specific job
            task_data_tuple = r_conn.brpop(task_queue_key, timeout=WORKER_CONFIG.BRPOP_TIMEOUT_SECONDS)
            if not task_data_tuple:
                # Timeout, no task received. Loop to check status or other queues.
                continue

            _queue_name, task_json_str = task_data_tuple
            task_message = json.loads(task_json_str.decode())

            job_id = task_message["job_id"]
            chunk_id = task_message["chunk_id"]
            start_specifier = task_message["start_specifier"] # e.g., start_line or start_byte
            end_specifier = task_message["end_specifier"]     # e.g., end_line or end_byte

            print(f"Worker {WORKER_CONFIG.ID}: Received task for job {job_id}, chunk {chunk_id}")

            # Add to in-progress set with a timestamp score for timeout monitoring
            r_conn.zadd(f"zset:inprogress:{job_id}", {chunk_id: time.time()})

            # Fetch job definition details (target_info, wordlist_path, chunk_definition_type)
            job_def_raw = r_conn.hgetall(f"job:{job_id}")
            job_details = {k.decode(): v.decode() for k, v in job_def_raw.items()}
            # Deserialize target_info if stored as JSON string
            job_details["target_info"] = json.loads(job_details.get("target_info_json_str", "{}"))
            
            wordlist_path = job_details.get("wordlist_path")
            chunk_def_type = job_details.get("chunk_definition_type") # "LINE_BASED" or "BYTE_RANGE"

            # Fetch wordlist chunk from storage
            # words: List[str] = storage.fetch_wordlist_chunk(
            #     wordlist_path, start_specifier, end_specifier, chunk_def_type
            # )
            words = ["example_word", "secret_password", "test_word"] # Placeholder for fetched words

            if words:
                process_chunk_words(job_id, chunk_id, words, job_details, r_conn)
            
            # Finalize task processing
            r_conn.hincrby(f"job_stats:{job_id}", "chunks_processed", 1)
            r_conn.zrem(f"zset:inprogress:{job_id}", chunk_id)
            print(f"Worker {WORKER_CONFIG.ID}: Completed chunk {chunk_id} for job {job_id}")

        except redis.exceptions.RedisError as e:
            print(f"Worker {WORKER_CONFIG.ID}: Redis error: {e}. Retrying connection or sleeping...")
            time.sleep(5) # Basic retry delay
        except Exception as e:
            print(f"Worker {WORKER_CONFIG.ID}: Unhandled error: {e}. Logging and continuing.")
            # More sophisticated error handling would be needed here,
            # potentially marking the chunk as failed or requeueing.
            # If task_message is defined, remove from in-progress to avoid false timeout
            if 'job_id' in locals() and 'chunk_id' in locals():
                 r_conn.zrem(f"zset:inprogress:{job_id}", chunk_id)
                 r_conn.hincrby(f"job_stats:{job_id}", "chunks_failed", 1) # Mark as failed
            time.sleep(1)


# if __name__ == "__main__":
#     # Proper initialization of r_conn and storage would go here
#     # based on loaded configurations from .env or config files.
#     class MockRedis: # Simple mock for snippet
#         def brpop(self, *args, **kwargs): return None
#         def hgetall(self, *args, **kwargs): return {}
#         def hget(self, *args, **kwargs): return None
#         def zadd(self, *args, **kwargs): pass
#         def zrem(self, *args, **kwargs): pass
#         def hincrby(self, *args, **kwargs): pass
#         def lpush(self, *args, **kwargs): pass
#     class MockStorage:
#         def fetch_wordlist_chunk(self, *args, **kwargs): return []
#     class MockWorkerConfig:
#         ID = "test-worker-01"
#         BRPOP_TIMEOUT_SECONDS = 5
#         PAUSE_POLL_INTERVAL_SECONDS = 10
#         TERMINAL_STATE_POLL_INTERVAL_SECONDS = 30
#     WORKER_CONFIG = MockWorkerConfig()
#     r_conn_mock = MockRedis()
#     storage_mock = MockStorage()
#     # worker_main_loop(r_conn_mock, storage_mock) # Uncomment to simulate
```

### B. API Server: Job Submission Endpoint (conceptual part of `app/api/v1/jobs.py`)

```python
from fastapi import FastAPI, HTTPException, BackgroundTasks, APIRouter
# from pydantic import BaseModel # Assuming models are in app.api.v1.models
import uuid
import time
import json # For target_info serialization
# from app.core.job_manager import enqueue_wordlist_chunks_task # Renamed for clarity
# from app.api.v1.models import JobSubmissionRequest, JobSubmissionResponse # Corrected model names
# from common.redis_client import get_redis_connection

# r_api: redis.Redis = get_redis_connection() # Global Redis connection for API
# jobs_router = APIRouter(prefix="/api/v1", tags=["Jobs"])

# @jobs_router.post("/jobs", response_model=JobSubmissionResponse, status_code=202)
# async def submit_new_job(job_request: JobSubmissionRequest, background_tasks: BackgroundTasks):
#     job_id = str(uuid.uuid4())
    
#     # Store core job definition in Redis
#     job_definition_payload = {
#         "job_id": job_id,
#         # Serialize complex objects like target_info to JSON strings for Redis Hash
#         "target_info_json_str": json.dumps(job_request.target_info), 
#         "wordlist_storage_type": job_request.wordlist_storage_type,
#         "wordlist_path": job_request.wordlist_path,
#         "chunk_definition_type": job_request.chunk_strategy.type,
#         "chunk_size": job_request.chunk_strategy.size,
#         "job_priority": job_request.job_priority,
#         "job_name": job_request.job_name or f"Job {job_id}",
#         "status": "PENDING_CHUNK_GENERATION", # Initial status before chunking starts
#         "submitted_at": time.time(),
#         "total_chunks": -1 # Will be updated by background task
#     }
#     r_api.hmset(f"job:{job_id}", job_definition_payload)
    
#     # Initialize job statistics
#     job_stats_payload = {
#         "status": "PENDING_CHUNK_GENERATION",
#         "chunks_processed": 0,
#         "chunks_failed": 0,
#         "results_found": 0,
#         "last_update_timestamp": time.time()
#     }
#     r_api.hmset(f"job_stats:{job_id}", job_stats_payload)

#     # Asynchronous task: Wordlist metadata fetching, chunk calculation, and task enqueuing
#     # This function (enqueue_wordlist_chunks_task) would be defined in app.core.job_manager or app.core.wordlist_processor
#     background_tasks.add_task(
#         enqueue_wordlist_chunks_task, 
#         job_id=job_id, 
#         wordlist_storage_type=job_request.wordlist_storage_type,
#         wordlist_path=job_request.wordlist_path,
#         chunk_strategy_type=job_request.chunk_strategy.type,
#         chunk_strategy_size=job_request.chunk_strategy.size
#     )
            
#     return JobSubmissionResponse(
#         job_id=job_id, 
#         message="Job accepted. Wordlist processing and task chunking initiated in background.",
#         status_url=f"/api/v1/jobs/{job_id}"
#     )

# # Placeholder for Pydantic models (would be in app/api/v1/models.py)
# class JobSubmissionRequest(BaseModel):
#     target_info: Dict[str, Any]
#     wordlist_storage_type: str
#     wordlist_path: str
#     chunk_strategy: Dict[str, Any] # e.g. {"type": "LINE_BASED", "size": 10000}
#     job_priority: int = 0
#     job_name: Optional[str] = None

# class JobSubmissionResponse(BaseModel):
#     job_id: str
#     message: str
#     status_url: str
```

### C. Utility: Wordlist Chunking Logic (conceptual part of `app/core/wordlist_processor.py`)

```python
# from common.storage_clients import get_storage_client, BaseStorageClient # To get metadata
# from common.redis_client import get_redis_connection
# import math
# import json
# import time # For logging/timestamps

# r_core: redis.Redis = get_redis_connection() # Global Redis connection for core logic

# def get_wordlist_metadata(wordlist_path: str, storage_type: str, storage_config: Dict) -> Dict[str, Any]:
#     """
#     Fetches metadata about the wordlist, e.g., size in bytes, and line count if line-based.
#     This is a complex operation for cloud storage if not downloading the file.
#     """
#     # storage: BaseStorageClient = get_storage_client(storage_type, storage_config)
#     # metadata = storage.get_file_metadata(wordlist_path) # This method needs to be implemented in BaseStorageClient
#     # Example:
#     # if metadata.get("type") == "LINE_BASED_COMPATIBLE_TEXT_FILE":
#     #     line_count = storage.count_lines(wordlist_path) # This could be expensive!
#     #     metadata["line_count"] = line_count
#     print(f"Simulating metadata fetch for {wordlist_path} using {storage_type}...")
#     time.sleep(2) # Simulate I/O and processing
#     # For LINE_BASED, "line_count" is essential. For BYTE_RANGE, "size_in_bytes" is.
#     return {"line_count": 1000000, "size_in_bytes": 50000000} # Dummy data

# def enqueue_wordlist_chunks_task(
#     job_id: str, 
#     wordlist_storage_type: str, 
#     wordlist_path: str, 
#     chunk_strategy_type: str, # "LINE_BASED" or "BYTE_RANGE"
#     chunk_strategy_size: int
# ):
#     """
#     Background task to calculate chunks and populate the Redis task queue for a job.
#     """
#     print(f"Job {job_id}: Starting chunk generation for wordlist {wordlist_path}")
#     try:
#         # storage_config would come from app.config or be passed down
#         metadata = get_wordlist_metadata(wordlist_path, wordlist_storage_type, {}) 
#         num_chunks = 0

#         if chunk_strategy_type == "LINE_BASED":
#             total_lines = metadata.get("line_count")
#             if total_lines is None:
#                 raise ValueError("Line count not available for LINE_BASED chunking.")
#             chunk_size = chunk_strategy_size
#             num_chunks = math.ceil(total_lines / chunk_size)
            
#             for i in range(num_chunks):
#                 start_line = i * chunk_size # 0-indexed start
#                 end_line = min((i + 1) * chunk_size - 1, total_lines - 1) # 0-indexed end, inclusive
#                 chunk_id = f"{job_id}_chunk_{i}"
#                 task_message = {
#                     "chunk_id": chunk_id,
#                     "job_id": job_id,
#                     "chunk_index": i,
#                     "start_specifier": start_line, # For LINE_BASED, this is start_line
#                     "end_specifier": end_line     # For LINE_BASED, this is end_line
#                 }
#                 r_core.lpush(f"queue:tasks:{job_id}", json.dumps(task_message))
        
#         elif chunk_strategy_type == "BYTE_RANGE":
#             total_bytes = metadata.get("size_in_bytes")
#             if total_bytes is None:
#                 raise ValueError("Total bytes not available for BYTE_RANGE chunking.")
#             chunk_size = chunk_strategy_size
#             num_chunks = math.ceil(total_bytes / chunk_size)

#             for i in range(num_chunks):
#                 start_byte = i * chunk_size
#                 end_byte = min((i + 1) * chunk_size - 1, total_bytes - 1)
#                 chunk_id = f"{job_id}_chunk_{i}"
#                 task_message = {
#                     "chunk_id": chunk_id,
#                     "job_id": job_id,
#                     "chunk_index": i,
#                     "start_specifier": start_byte, # For BYTE_RANGE, this is start_byte
#                     "end_specifier": end_byte     # For BYTE_RANGE, this is end_byte
#                 }
#                 r_core.lpush(f"queue:tasks:{job_id}", json.dumps(task_message))
#         else:
#             raise ValueError(f"Unsupported chunk strategy type: {chunk_strategy_type}")

#         # Update job definition and stats after successful chunking
#         r_core.hmset(f"job:{job_id}", {"total_chunks": num_chunks, "status": "PENDING_DISPATCH"})
#         r_core.hset(f"job_stats:{job_id}", "status", "PENDING_DISPATCH") # Ready for workers
#         print(f"Job {job_id}: Successfully enqueued {num_chunks} tasks.")

#     except Exception as e:
#         error_message = f"Chunk generation failed: {str(e)}"
#         print(f"Job {job_id}: {error_message}")
#         r_core.hmset(f"job:{job_id}", {"status": "FAILED_CHUNK_GENERATION", "error_message": error_message})
#         r_core.hset(f"job_stats:{job_id}", "status", "FAILED")

```

These conceptual snippets illustrate the division of responsibilities and the key data flows within the proposed project structure. A full implementation would require careful attention to detail in error handling, configuration management, security, and the specific logic of target interaction and wordlist parsing.
