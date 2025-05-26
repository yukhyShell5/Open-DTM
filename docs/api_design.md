# FastAPI API Design for Distributed Brute-Force Framework

## 1. Introduction

### Purpose of the API

The API for the Distributed Brute-Force Framework provides a programmatic interface for external clients (e.g., a CLI tool, a web UI, or other scripts) to interact with the system. Its core functionalities include:
*   Submitting new brute-force jobs.
*   Monitoring the status and progress of ongoing jobs.
*   Controlling jobs (e.g., pausing and resuming).
*   Retrieving results from completed or running jobs.

This document outlines the conceptual design of the API endpoints and their interactions with the underlying system components, primarily Redis.

## 2. General Conventions

### Base URL

All API endpoints are prefixed with `/api/v1`.
Example: `http://localhost:8000/api/v1/jobs`

### Authentication

For the initial design and educational purposes, authentication is **not covered**. In a production environment, this would be essential. Potential mechanisms include:
*   **API Key Authentication:** Clients provide a pre-shared API key via an HTTP header (e.g., `X-API-Key`).
*   **OAuth2:** For more complex scenarios, especially with third-party integrations.

### Error Responses

The API will use standard HTTP status codes to indicate the success or failure of a request. Error responses will follow a common JSON schema:

```json
{
    "detail": "A human-readable error message describing the issue."
}
```

Common error codes include:
*   `400 Bad Request`: Invalid request payload or parameters.
*   `401 Unauthorized`: Authentication failed (if implemented).
*   `403 Forbidden`: Authenticated user does not have permission.
*   `404 Not Found`: Requested resource does not exist.
*   `409 Conflict`: Request conflicts with the current state of the resource (e.g., trying to resume a completed job).
*   `500 Internal Server Error`: An unexpected error occurred on the server.

## 3. API Endpoints

### A. Submit New Job

*   **HTTP Method and Path:** `POST /jobs`
*   **Description:**
    Submits a new brute-force job to the framework. The API server generates a unique `job_id` for the job. It then creates the job's definition and initial status in Redis. Crucially, it initiates the process of accessing the specified wordlist, calculating chunk boundaries based on the provided strategy, and populating the task queue in Redis (`queue:tasks:<job_id>`) with these chunks. This chunking process may be asynchronous to avoid blocking the API response for large wordlists.
*   **Request Body:**
    *   Schema (Conceptual Pydantic Model):
        ```python
        class TargetInfo(BaseModel):
            # Flexible, depends on brute-force type. Examples:
            # For hash cracking:
            # hash_value: str
            # hash_type: str # e.g., "sha256", "md5"
            # salt: Optional[str] = None

            # For web login:
            url: str
            method: str = "POST" # "GET", "POST"
            username_field: str
            password_field: str
            additional_data: Optional[dict] = None # Other form fields
            success_indicator: str # Text/regex on page to indicate success

        class ChunkStrategy(BaseModel):
            type: Literal["LINE_BASED", "BYTE_RANGE"] # Corrected from BYTE_BASED
            size: int # Number of lines or bytes per chunk

        class JobSubmissionRequest(BaseModel):
            target_info: TargetInfo
            wordlist_storage_type: Literal["s3", "minio", "nfs"] # Define supported types
            wordlist_path: str # Full path/URI to the wordlist
            chunk_strategy: ChunkStrategy
            job_priority: int = 0 # Optional: 0 default, higher for more priority
            job_name: Optional[str] = None # Optional user-friendly name
        ```
    *   JSON Example:
        ```json
        {
            "target_info": {
                "hash_value": "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8",
                "hash_type": "sha256"
            },
            "wordlist_storage_type": "s3",
            "wordlist_path": "s3://mybucket/wordlists/rockyou.txt",
            "chunk_strategy": {
                "type": "LINE_BASED",
                "size": 10000
            },
            "job_priority": 1,
            "job_name": "SHA256 RockYou Test"
        }
        ```
*   **Path Parameters:** None
*   **Query Parameters:** None
*   **Successful Response Body (202 Accepted):**
    Indicates that the job submission has been received and the system is preparing it. The actual chunking and task queue population might happen asynchronously.
    ```json
    {
        "job_id": "generated_unique_job_id_uuid",
        "message": "Job accepted. Chunking and task queue population initiated.",
        "status_url": "/api/v1/jobs/generated_unique_job_id_uuid"
    }
    ```
*   **Error Responses:**
    *   `400 Bad Request`: Invalid request payload (e.g., missing required fields, invalid `wordlist_storage_type`, inaccessible `wordlist_path`).
    *   `500 Internal Server Error`: If the server fails to initiate the job (e.g., cannot connect to Redis).
*   **Interaction with Redis:**
    *   Generates a unique `job_id` (e.g., using UUID).
    *   Creates the job definition hash: `HSET job:<job_id> target_info "..." wordlist_path "..." ... status "PENDING" submitted_at <timestamp>`.
    *   Initializes the job statistics hash: `HMSET job_stats:<job_id> status "PENDING" chunks_processed 0 chunks_failed 0 results_found 0`.
    *   **Asynchronously (important for large wordlists):**
        *   Calls the wordlist chunking logic (see section 4).
        *   This logic calculates total chunks, updates `job:<job_id>::total_chunks`.
        *   Populates `queue:tasks:<job_id>` with task messages using `LPUSH` for each chunk.
        *   Once chunking is complete and tasks are enqueued, updates `job_stats:<job_id>::status` to `SUBMITTED` or `RUNNING` (if workers can pick up tasks immediately).

### B. Get Job Status and Progress

*   **HTTP Method and Path:** `GET /jobs/{job_id}`
*   **Description:** Retrieves the current status, progress, definition, and basic statistics of a specific job.
*   **Request Body:** None
*   **Path Parameters:**
    *   `job_id: str` (Path parameter, e.g., a UUID)
*   **Query Parameters:** None
*   **Successful Response Body (200 OK):**
    ```json
    {
        "job_id": "some_job_id",
        "definition": { // Data primarily from job:<job_id>
            "target_info": { "hash_value": "...", "hash_type": "sha256" },
            "wordlist_storage_type": "s3",
            "wordlist_path": "s3://mybucket/wordlists/rockyou.txt",
            "chunk_strategy": { "type": "LINE_BASED", "size": 10000 },
            "job_priority": 1,
            "job_name": "SHA256 RockYou Test",
            "total_chunks": 150, // Calculated after chunking
            "submitted_at": "iso_timestamp"
        },
        "stats": { // Data primarily from job_stats:<job_id>
            "status": "RUNNING", // e.g., PENDING, SUBMITTED, RUNNING, PAUSED, COMPLETED_SUCCESS, COMPLETED_NOTFOUND, FAILED
            "chunks_processed": 75,
            "chunks_failed": 2,
            "results_found": 1,
            "started_at": "iso_timestamp", // When first worker picked up a task
            "completed_at": "iso_timestamp", // If completed
            "last_update_timestamp": "iso_timestamp" // Last time any worker updated stats
        },
        "estimated_completion_percentage": 50.0 // Calculated: (chunks_processed / total_chunks) * 100
    }
    ```
*   **Error Responses:**
    *   `404 Not Found`: If `job_id` does not exist in Redis.
*   **Interaction with Redis:**
    *   Reads all fields from `job:<job_id>` using `HGETALL`.
    *   Reads all fields from `job_stats:<job_id>` using `HGETALL`.

### C. Pause Job

*   **HTTP Method and Path:** `POST /jobs/{job_id}/pause`
*   **Description:** Requests to pause a running or submitted job. Workers subscribed to this job will stop fetching new tasks for it. Tasks currently in progress might complete.
*   **Request Body:** None
*   **Path Parameters:**
    *   `job_id: str`
*   **Query Parameters:** None
*   **Successful Response Body (200 OK):**
    ```json
    {
        "job_id": "some_job_id",
        "status": "PAUSED",
        "message": "Job pause request accepted. Workers will cease processing new chunks for this job once current chunks are finished or if they check status before starting new ones."
    }
    ```
*   **Error Responses:**
    *   `404 Not Found`: If `job_id` does not exist.
    *   `409 Conflict`: If the job is already in a terminal state (e.g., `COMPLETED_SUCCESS`, `COMPLETED_NOTFOUND`, `FAILED`) or already `PAUSED`.
*   **Interaction with Redis:**
    *   Updates `status` field in `job:<job_id>` to `PAUSED`.
    *   Updates `status` field in `job_stats:<job_id>` to `PAUSED`.

### D. Resume Job

*   **HTTP Method and Path:** `POST /jobs/{job_id}/resume`
*   **Description:** Resumes a job that was previously paused. Workers will start fetching tasks for this job again.
*   **Request Body:** None
*   **Path Parameters:**
    *   `job_id: str`
*   **Query Parameters:** None
*   **Successful Response Body (200 OK):**
    ```json
    {
        "job_id": "some_job_id",
        "status": "RUNNING",
        "message": "Job resume request accepted. Workers will now pick up tasks for this job."
    }
    ```
*   **Error Responses:**
    *   `404 Not Found`: If `job_id` does not exist.
    *   `409 Conflict`: If the job is not currently in a `PAUSED` state (e.g., it's already `RUNNING`, `COMPLETED_SUCCESS`, `FAILED`).
*   **Interaction with Redis:**
    *   Updates `status` field in `job:<job_id>` to `RUNNING` (or its previous active state like `SUBMITTED` if no tasks were processed yet).
    *   Updates `status` field in `job_stats:<job_id>` to `RUNNING`.

### E. Get Job Results

*   **HTTP Method and Path:** `GET /jobs/{job_id}/results`
*   **Description:** Retrieves the list of successful results (e.g., found passwords or credentials) for a job. This can be called for jobs that are running or completed.
*   **Request Body:** None
*   **Path Parameters:**
    *   `job_id: str`
*   **Query Parameters:**
    *   `limit: int = 100` (Maximum number of results to return per page)
    *   `offset: int = 0` (Number of results to skip, for pagination)
*   **Successful Response Body (200 OK):**
    ```json
    {
        "job_id": "some_job_id",
        "results": [
            // Examples of result items. Could be simple strings or structured JSON.
            // This structure should align with what workers push to the results list.
            { "value": "password123", "timestamp": "2023-10-28T12:30:00Z", "chunk_id": "chunk_abc" },
            "another_password"
        ],
        "pagination": {
            "limit": 100,
            "offset": 0,
            "total_results_in_job": 2, // Total number of results found for this job so far
            "returned_results": 2 // Number of results in the current response
        }
    }
    ```
*   **Error Responses:**
    *   `404 Not Found`: If `job_id` does not exist.
*   **Interaction with Redis:**
    *   Reads from the list `list:results:<job_id>` using `LRANGE job_id_results_list offset (offset + limit - 1)`.
    *   Gets the total number of results using `LLEN list:results:<job_id>`.

## 4. Wordlist Chunking Process (API Server Role)

Upon job submission (`POST /jobs`), the API server is responsible for initiating the wordlist chunking process. This is a critical step and can be resource-intensive for large wordlists.

1.  **Receive Submission:** The API receives the job submission request including `wordlist_path`, `wordlist_storage_type`, and `chunk_strategy`.
2.  **Validate Path & Access (Initial Check):** Perform a basic validation of the `wordlist_path` format and, if possible, check for the existence of the wordlist (e.g., an S3 HEAD request). This initial check should be quick.
3.  **Acknowledge Request (202 Accepted):** Return a response to the client quickly, indicating the job is accepted and chunking is underway.
4.  **Asynchronous Chunking Task:** Spawn a background task (e.g., using FastAPI's `BackgroundTasks`, Celery, or a separate microservice) to handle the actual chunking. This prevents blocking API worker threads.
    *   **Access Wordlist Metadata:**
        *   **NFS:** Use standard file system operations to get file size. For `LINE_BASED` chunking, count lines (e.g., `wc -l` or stream and count).
        *   **S3/MinIO:**
            *   Use `head_object` to get `ContentLength` (file size in bytes).
            *   For `LINE_BASED` chunking, line counting is more complex:
                *   It might involve downloading the file (if small enough).
                *   Using S3 Select with an SQL query like `SELECT count(*) FROM s3object` (if the object is plain text and S3 Select is supported).
                *   Streaming the file and counting lines.
                *   If an exact line count is too slow to obtain, the system might require the user to provide it, or use an estimation based on file size and average line length (less accurate).
    *   **Calculate Chunk Definitions:** Based on `chunk_strategy.type` (`LINE_BASED` or `BYTE_RANGE`) and `chunk_strategy.size`:
        *   Determine `total_chunks`.
        *   For each chunk, calculate its `start_specifier` (start line/byte) and `end_specifier` (end line/byte).
    *   **Update Redis:**
        *   Store `total_chunks` in `job:<job_id>`.
    *   **Populate Task Queue:** For each calculated chunk, create a task message (JSON string with `chunk_id`, `job_id`, `start_specifier`, `end_specifier`) and push it to `queue:tasks:<job_id>` in Redis (e.g., using `LPUSH`).
    *   **Update Job Status:** Once all tasks are enqueued, update `job_stats:<job_id>::status` to `SUBMITTED` (or `RUNNING` if workers can immediately start).

This asynchronous handling ensures the API remains responsive even when dealing with very large wordlists that take time to process for chunking.
