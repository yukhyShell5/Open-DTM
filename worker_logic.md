# Worker Node Logic for Distributed Brute-Force Framework

## 1. Introduction

Worker nodes are the computational backbone of the distributed brute-force framework. Their primary role is to execute assigned tasks, which involve processing a specific chunk of a wordlist against a given target. They fetch tasks from a central queue, retrieve the corresponding wordlist data, perform the brute-force attempts, and report results and progress back to the system.

## 2. Configuration

Each worker node requires several configuration parameters to operate correctly. These can be provided through environment variables, a configuration file (e.g., YAML, JSON, .env), or command-line arguments.

*   **`WORKER_ID`**: A unique identifier for the worker (e.g., `worker-hostname-01`, a UUID). Useful for logging and tracking.
*   **`REDIS_HOST`**: Hostname or IP address of the Redis server.
*   **`REDIS_PORT`**: Port number for the Redis server (default: 6379).
*   **`REDIS_PASSWORD`**: (Optional) Password for Redis authentication.
*   **`REDIS_DB`**: (Optional) Redis database number (default: 0).
*   **Wordlist Storage Credentials (depending on the solution):**
    *   **S3/MinIO:**
        *   `S3_ENDPOINT_URL` (for MinIO or other S3-compatible services)
        *   `AWS_ACCESS_KEY_ID`
        *   `AWS_SECRET_ACCESS_KEY`
        *   `S3_REGION` (Optional, depending on S3 provider)
    *   **NFS:** No specific credentials here, but the worker machine must have the NFS share mounted and accessible.
*   **`MAX_RETRIES_WORDLIST_FETCH`**: Number of times to retry fetching a wordlist chunk (e.g., 3).
*   **`LOG_LEVEL`**: Logging verbosity (e.g., `INFO`, `DEBUG`).
*   **`POLL_TIMEOUT_SECONDS`**: Timeout for `BRPOP` when fetching tasks from Redis (e.g., 5 seconds). This allows the worker to periodically check for other signals or job status changes.

## 3. Initialization

When a worker node starts, it performs the following steps:

1.  **Load Configuration:** Read and parse configuration from environment variables or a config file. Validate essential parameters.
2.  **Initialize Logger:** Set up a logging mechanism (e.g., Python's `logging` module) based on `LOG_LEVEL`.
3.  **Establish Redis Connection:**
    *   Connect to the Redis server using the provided connection details.
    *   Verify the connection (e.g., by sending a `PING` command).
4.  **Initialize Wordlist Storage Client:**
    *   **S3/MinIO:** Create an S3 client instance (e.g., `boto3.client('s3', ...)`), configured with the endpoint URL and credentials.
    *   **NFS:** Ensure the NFS mount point is accessible. No specific client initialization might be needed beyond standard file system operations.
5.  **Register/Log Startup (Optional):**
    *   The worker might log its startup event to a central logging system or a specific Redis key (e.g., adding its `WORKER_ID` to a `set:active_workers` with a timestamp). This can help in monitoring active workers.
    *   Log `WORKER_ID` and key configuration details at startup for traceability.

## 4. Main Processing Loop

The worker operates in a continuous loop, fetching and processing tasks.

```
LOOP FOREVER:
    task_data = FETCH_TASK_FROM_REDIS()

    IF task_data IS NULL (e.g., BRPOP timeout):
        CONTINUE LOOP  // No task available, try again

    job_id = task_data.job_id
    chunk_id = task_data.chunk_id

    // Check job status before processing
    job_status = GET_JOB_STATUS_FROM_REDIS(job_id)
    IF job_status == "PAUSED" OR job_status == "CANCELLED":
        REQUEUE_TASK(task_data) // Put back in original queue or a holding queue
        WAIT_SHORT_PERIOD() // Avoid busy-looping on a paused job
        CONTINUE LOOP

    MARK_TASK_IN_PROGRESS(job_id, chunk_id)

    wordlist_chunk_content = FETCH_WORDLIST_CHUNK(job_id, task_data.start_specifier, task_data.end_specifier)

    IF wordlist_chunk_content IS NULL (fetch failed after retries):
        REPORT_CHUNK_FAILURE(job_id, chunk_id)
        FINALIZE_TASK_FAILURE(job_id, chunk_id)
        CONTINUE LOOP

    target_info = GET_TARGET_INFO_FROM_REDIS(job_id) // Contains hash, type, etc.

    PROCESS_CHUNK(wordlist_chunk_content, target_info, job_id, chunk_id)

    FINALIZE_TASK_SUCCESS(job_id, chunk_id)
END LOOP
```

### 4.1. Fetch Task

1.  **Listen to Queues:** The worker listens to one or more job-specific task queues. For simplicity, let's assume it knows the `job_id` it should work on, or it polls a list of active job queues. A common pattern is `queue:tasks:<job_id>`.
    *   Example: `task_tuple = redis.brpop('queue:tasks:jobXYZ', timeout=POLL_TIMEOUT_SECONDS)`
2.  **Parse Task:** If `brpop` returns data, it's typically a tuple `(queue_name, task_json_string)`. Parse the JSON string to get `chunk_id`, `job_id`, `start_line`/`start_specifier`, `end_line`/`end_specifier`.
3.  **Handle Timeout:** If `brpop` times out (`task_tuple` is `None`), the loop continues, and it tries fetching again. This allows the worker to remain responsive to shutdown signals or other commands.
4.  **Check Job Status:** Before starting any processing, query `job_stats:<job_id>::status`. If the job is `PAUSED` or `CANCELLED`:
    *   The task should be requeued to its original queue using `LPUSH`.
    *   The worker should then wait for a short period or listen to a different queue to avoid repeatedly fetching and requeueing tasks for a paused job.

### 4.2. Mark Task In-Progress

1.  Once a valid task is fetched and the job is active:
    *   Add the `chunk_id` to the job's in-progress sorted set:
        `redis.zadd(f'zset:inprogress:{job_id}', {chunk_id: time.time()})`
    *   This helps monitor tasks and identify those that might be stuck or orphaned if a worker crashes.

### 4.3. Fetch Wordlist Chunk

1.  **Get Job Details:** Retrieve `wordlist_path` and potentially other relevant info (like `chunk_definition_type`) from the `job:<job_id>` hash in Redis.
2.  **Access Storage:**
    *   **S3/MinIO:** Use the S3 client and the task's `start_specifier`/`end_specifier`.
        *   For line-based chunking: This might involve streaming the object and iterating line by line, or if the object store supports it, using S3 Select to fetch specific line ranges. Simpler implementations might download a byte range that is expected to contain the lines and then filter locally.
        *   For byte-range chunking: Use HTTP `Range` headers (e.g., `s3_client.get_object(Bucket=..., Key=..., Range=f'bytes={start_offset}-{end_offset}')`).
    *   **NFS:** Open the file at `wordlist_path`. Seek to the `start_line` (by reading and discarding lines) or `start_offset` (using `file.seek()`) and read until `end_line` or `end_offset`.
3.  **Retry Logic:** Implement retries (e.g., up to `MAX_RETRIES_WORDLIST_FETCH`) with exponential backoff for transient network errors during fetch. If all retries fail, the chunk fetch is considered failed.

### 4.4. Process Chunk (Brute-Force Attempt)

1.  Iterate through each `word` in the fetched `wordlist_chunk_content`.
2.  For each `word`:
    *   `attempt_status = perform_attempt(word, target_info)` (see section 5).
    *   `target_info` was fetched from `job:<job_id>`.
    *   If `attempt_status == "SUCCESS"`:
        *   Report the found `word` (and `job_id`) to `list:results:<job_id>` in Redis:
            `redis.lpush(f'list:results:{job_id}', json.dumps({"word": word, "timestamp": time.time()}))`
        *   Increment the `results_found` counter in `job_stats:<job_id>`:
            `redis.hincrby(f'job_stats:{job_id}', 'results_found', 1)`
        *   **Decision:** Depending on job configuration (e.g., "find first" vs "find all"):
            *   Stop processing the current chunk and proceed to finalize.
            *   Or, continue processing other words in the chunk.
        *   Update job status to `COMPLETED_SUCCESS` in `job_stats:<job_id>::status` if this is the first find and the job should stop.
            `redis.hset(f'job_stats:{job_id}', 'status', 'COMPLETED_SUCCESS')`

### 4.5. Update Status & Finalize Task

This section covers actions after a chunk is processed, whether successfully or due to an error that stops further processing of this specific chunk.

*   **Increment Processed Count:** Atomically increment `chunks_processed` in `job_stats:<job_id>`:
    `redis.hincrby(f'job_stats:{job_id}', 'chunks_processed', 1)`
*   **Update Timestamp:** Set `last_update_timestamp` in `job_stats:<job_id>`:
    `redis.hset(f'job_stats:{job_id}', 'last_update_timestamp', time.time())`
*   **Remove from In-Progress:** Remove the `chunk_id` from `zset:inprogress:<job_id>`:
    `redis.zrem(f'zset:inprogress:{job_id}', chunk_id)`
*   **Check for Job Completion (Worker Tentative Check):**
    1.  Fetch `total_chunks` from `job:<job_id>` and current `chunks_processed` from `job_stats:<job_id>`.
    2.  If `chunks_processed == total_chunks`:
        *   Fetch `results_found` from `job_stats:<job_id>`.
        *   If `results_found > 0`, the status should ideally already be `COMPLETED_SUCCESS`.
        *   If `results_found == 0`, the worker can tentatively set `job_stats:<job_id>::status` to `COMPLETED_NOTFOUND`.
            `current_status = redis.hget(f'job_stats:{job_id}', 'status')`
            `IF current_status NOT IN ['COMPLETED_SUCCESS', 'FAILED', 'CANCELLED']:`
                `redis.hset(f'job_stats:{job_id}', 'status', 'COMPLETED_NOTFOUND')`
        *   The API server or a dedicated monitoring component would perform the authoritative check and final job status update.

## 5. `perform_attempt(word, target_info)` Function (Conceptual)

This function is the core of the brute-force logic and is highly application-specific.
*   **Inputs:**
    *   `word`: The current word/password candidate from the wordlist.
    *   `target_info`: A dictionary/object containing details about the target.
        *   Example (hash cracking): `{"type": "sha256", "hash_value": "...", "salt": "..."}`
        *   Example (service login): `{"service": "ssh", "ip": "...", "port": 22, "username": "admin"}`
*   **Logic:**
    *   For hash cracking (educational simulation):
        ```python
        def perform_attempt(word, target_info):
            # In a real scenario, apply salting if present, then hash
            hashed_word = hashlib.sha256(word.encode()).hexdigest() # Simplified
            if hashed_word == target_info['hash_value']:
                return "SUCCESS"
            return "FAILURE"
        ```
    *   For service login: This would involve network requests, handling responses, etc.
*   **Return Values:**
    *   `"SUCCESS"`: The `word` is correct.
    *   `"FAILURE"`: The `word` is incorrect.
    *   `"ERROR_RETRYABLE"`: A temporary error occurred (e.g., network timeout, service rate limit). The attempt for this word (or the whole chunk) could be retried.
    *   `"ERROR_FATAL"`: An unrecoverable error occurred (e.g., invalid target configuration, authentication scheme changed).

## 6. Error Handling

Robust error handling is critical for a distributed system.

*   **Task Fetch Failure (Redis unavailable):**
    *   Log the error.
    *   Implement a retry loop with exponential backoff.
    *   If connection cannot be re-established after several retries, the worker might need to exit gracefully or enter a long wait state.
*   **Wordlist Chunk Fetch Failure:**
    *   Retry the fetch operation (as configured by `MAX_RETRIES_WORDLIST_FETCH`) with backoff.
    *   If all retries fail:
        *   Log the error comprehensively (job ID, chunk ID, storage path, error details).
        *   Increment `chunks_failed` in `job_stats:<job_id>`:
            `redis.hincrby(f'job_stats:{job_id}', 'chunks_failed', 1)`
        *   Optionally, move the failed `chunk_id` or task message to a separate Redis list for failed chunks (e.g., `queue:failed_chunks:<job_id>`) for later inspection.
        *   Remove the task from `zset:inprogress:<job_id>`.
*   **`perform_attempt` Error:**
    *   **`ERROR_RETRYABLE`**:
        *   Log the error.
        *   Strategy 1: Requeue the entire chunk (if errors are likely to affect the whole chunk or target). Add back to `queue:tasks:<job_id>` (perhaps with a delay mechanism or to a separate retry queue).
        *   Strategy 2 (more complex): If the error is specific to a word or a small set of words, and the task can be made more granular, retry only those words. This is often too complex for simple brute-force.
    *   **`ERROR_FATAL`**:
        *   Log the error extensively.
        *   Mark the chunk as failed (increment `chunks_failed`, move to failed queue).
        *   It might be necessary to alert an administrator or mark the entire job as `FAILED` if the error indicates a fundamental problem with the job setup.
*   **Reporting Errors:**
    *   Use structured logging.
    *   Critical errors (e.g., persistent Redis connection failure, fundamental job issues) could also be pushed to a dedicated Redis list (e.g., `list:system_errors`) for centralized monitoring.

## 7. Graceful Shutdown

Workers should handle termination signals (`SIGINT`, `SIGTERM`) gracefully.

1.  **Signal Handler:** Set up signal handlers for `SIGINT` and `SIGTERM`.
2.  **Set Shutdown Flag:** Upon receiving a signal, set a global shutdown flag to `True`.
3.  **Stop Accepting New Tasks:** The main loop, after fetching a task or after `BRPOP` timeout, should check this flag. If `True`, it should not fetch new tasks and break the loop.
4.  **Complete Current Task (Optional):**
    *   If a task is currently being processed, the worker can try to complete it, especially if it's close to finishing the chunk.
    *   For very long-running chunks or `perform_attempt` calls, it might be necessary to interrupt, save state (if possible), and requeue the task. This requires careful design of `perform_attempt` to be interruptible.
5.  **Cleanup:**
    *   Remove itself from any active worker set in Redis (if used).
    *   Close the Redis connection.
    *   Close the S3/NFS client (if applicable).
6.  **Log Shutdown:** Log that the worker is shutting down gracefully.

## 8. Scalability

The worker architecture is designed for horizontal scalability:
*   Multiple worker instances can be run on the same machine or, more typically, across many different machines or containers.
*   Each worker operates independently, connecting to the shared Redis instance for task coordination and the shared wordlist storage for data.
*   The number of workers can be scaled up or down based on the desired processing power and the number of active jobs.
*   Load balancing is achieved by workers pulling tasks from the common Redis queues.

This decentralized approach allows the framework to leverage distributed computing resources effectively.
