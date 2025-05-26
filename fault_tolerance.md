# Fault Tolerance and Resumability in Distributed Brute-Force Framework

## 1. Introduction

In a distributed system designed for potentially long-running tasks like brute-force operations, fault tolerance and resumability are paramount.
*   **Fault Tolerance:** The ability of the system to continue operating correctly, perhaps at a reduced capacity, in the event of one or more component failures. This prevents a single failure from bringing down the entire process.
*   **Resumability:** The capability to pause and later resume jobs, or to recover from interruptions (like component failures or planned restarts) and continue processing from where it left off, minimizing lost work.

This document outlines the mechanisms implemented in the distributed brute-force framework to achieve these goals.

## 2. Worker Node Failure Handling

### Detection

The primary mechanism for detecting worker failure or significantly stalled tasks relies on monitoring the tasks currently marked as "in-progress."

*   **`zset:inprogress:<job_id>`:** This Redis Sorted Set is key.
    *   When a worker picks up a task (a `chunk_id`), it adds the `chunk_id` to this ZSET with the current Unix timestamp as its score: `ZADD zset:inprogress:<job_id> <timestamp> <chunk_id>`.
*   **Monitor Process:** A separate monitor process (which could be a thread within the API server or a standalone utility) periodically scans these ZSETs for all active jobs.
    *   For each `chunk_id` in a ZSET, it compares the score (task start timestamp) with the current time.
    *   If `current_time - task_start_time > configured_timeout`, the task is considered stale or timed-out, implying the worker assigned to it may have failed or is stuck.

### Recovery

Once a stale task is identified:

1.  **Re-queue Task:** The monitor process removes the `chunk_id` from `zset:inprogress:<job_id>` using `ZREM`.
2.  It then adds the `chunk_id` (or the full task message if stored/reconstructible) back to the primary task queue for that job, `queue:tasks:<job_id>`. It's preferable to use `LPUSH` to add it to the front of the queue, ensuring it's picked up relatively quickly.
3.  **Logging & Metrics:**
    *   The event (timed-out task being re-queued) should be logged with `job_id` and `chunk_id`.
    *   Optionally, a counter for timeouts or re-queued tasks can be incremented in `job_stats:<job_id>` (e.g., `hincrby job_stats:<job_id> chunks_timedout 1`). This can help in identifying problematic jobs or workers.

### Considerations

*   **`configured_timeout` Value:** This timeout duration is critical.
    *   **Too short:** May lead to false positives, where tasks are re-queued even if the worker is just slow but still active. This can cause unnecessary reprocessing.
    *   **Too long:** Delays recovery from actual worker failures, leading to longer idle times for those tasks.
    *   The optimal value depends on the expected maximum processing time for a single chunk, plus a buffer. It should be configurable.
*   **At-Least-Once Delivery:** This recovery mechanism implies that a task might be processed more than once. If a worker fails just after completing a chunk but before removing it from the in-progress set, the task will be re-queued and processed again by another worker.
    *   **Idempotency:** The `perform_attempt` logic and result storage should ideally be idempotent. For simple password finding, if `list:results:<job_id>` is a Redis List, duplicate found passwords might be stored. If it's a Set, duplicates are naturally handled. If results are stored in an external database, application logic must handle potential duplicates.
    *   The impact of reprocessing is usually acceptable (some wasted computation) compared to losing tasks.

## 3. Job Pause and Resume

This feature allows users to temporarily halt and later continue jobs, useful for managing resources or responding to external factors.

### Pausing a Job

1.  **User Action:** Initiated via an API call, e.g., `POST /api/jobs/{job_id}/pause`.
2.  **API Server:**
    *   Updates the job's status in the main definition: `HSET job:<job_id> status PAUSED`.
    *   Updates the job's operational status: `HSET job_stats:<job_id> status PAUSED`.
    *   (Optionally) Broadcast a "pause" message via Redis Pub/Sub to a channel workers might be listening to for immediate effect, though polling `job_stats` is the more robust approach.

### Worker Behavior (Pause)

*   **Before Fetching Task:** When a worker attempts to fetch a new task for a specific `job_id`, it should first check `HGET job_stats:<job_id> status`. If the status is `PAUSED`, the worker should:
    *   Avoid polling `queue:tasks:<job_id>`.
    *   Wait for a period (e.g., using `sleep`) or switch to polling tasks for other active (non-paused) jobs if it's designed to handle multiple jobs.
*   **During Chunk Processing:** If a job is paused while a worker is actively processing one of its chunks:
    *   **Ideal:** The worker completes the current chunk, reports its results/progress as usual, and then, before fetching a new task, it will see the `PAUSED` status.
    *   **Immediate Stop (More Complex):** For very long chunks, a worker could periodically check the job status mid-chunk. If paused, it might attempt to save its progress within the chunk (if feasible, which is complex) and stop, or simply stop and let the chunk be re-processed later. The simpler approach is to finish the current chunk.

### Resuming a Job

1.  **User Action:** Initiated via an API call, e.g., `POST /api/jobs/{job_id}/resume`.
2.  **API Server:**
    *   Updates the job's status in the main definition: `HSET job:<job_id> status RUNNING`.
    *   Updates the job's operational status: `HSET job_stats:<job_id> status RUNNING`.

### Worker Behavior (Resume)

*   As workers periodically check job statuses or attempt to `BRPOP` from `queue:tasks:<job_id>`, they will see the status as `RUNNING` (or tasks will become available in the queue).
*   They will naturally resume fetching and processing tasks for this job without needing a direct "resume" command.

## 4. API Server / Orchestrator Failure

### Stateless API Server Design

*   The API server is designed to be as stateless as possible regarding ongoing job progress. All critical persistent data—job definitions, task queues, in-progress tasks, job statistics, and results—is stored in Redis.
*   If the API server process crashes or is restarted:
    *   It can safely restart.
    *   Upon restart, it can query Redis to reconstruct its understanding of current jobs for user queries or management operations.
    *   No ongoing work by workers is directly affected as long as Redis remains available. Workers continue to fetch tasks, process them, and report to Redis.

### Monitor Process Failure

The monitor process, responsible for detecting and requeueing timed-out tasks from `zset:inprogress:<job_id>`, is also critical.

*   **Collocated with API Server:** If the monitor is a thread within the API server, it fails when the API server fails. Upon API server restart, the monitor thread also restarts and resumes its function.
*   **Separate Monitor Process:** Running the monitor as a separate, lightweight process is a good strategy.
    *   This process can be monitored and restarted independently (e.g., by systemd, Supervisor, or a container orchestrator).
    *   **High Availability for Monitor:** To avoid the monitor itself being a single point of failure, multiple instances of the monitor process can be run. They can use a Redis-based distributed lock (e.g., `SET job_monitor_lock <instance_id> NX EX <lock_timeout>`) to ensure only one instance is actively performing monitoring duties at any given time. Others would be on standby.

### Impact of API Server Unavailability

*   **Job Processing:** Existing jobs continue to be processed by workers as they interact directly with Redis.
*   **Control Plane:** New job submissions, status queries, pause/resume commands, and result retrieval via the API will be unavailable until the API server is restored.

## 5. Redis Failure

Redis is the central nervous system of the framework. Its availability is critical.

*   **Single Point of Failure (Default):** In a default, standalone Redis deployment, if the Redis server crashes, the entire system halts:
    *   Workers cannot fetch tasks or report progress/results.
    *   The API server cannot access job data or submit new jobs.
    *   The monitor process cannot function.

### Mitigation Strategies (Briefly Mention)

*   **Redis Persistence (RDB/AOF):**
    *   **RDB (Snapshotting):** Periodically saves the dataset to disk. Data loss can occur between snapshots.
    *   **AOF (Append-Only File):** Logs every write operation. More durable but can be slower.
    *   **Purpose:** Allows Redis to reload data after a restart, recovering job queues, states, etc., up to the last persistence point. This helps in resuming operations after Redis itself crashes and is restarted, but doesn't provide high availability.
*   **Redis Sentinel (High Availability):**
    *   Provides a high-availability solution with automatic failover.
    *   A master Redis instance handles writes, and one or more replica instances mirror the data.
    *   Sentinel processes monitor the master. If the master fails, Sentinels coordinate to promote a replica to be the new master.
    *   Application clients (API server, workers, monitor) must be configured to connect to Sentinel, which then provides the address of the current master. This significantly improves uptime.
*   **Redis Cluster (Distributed):**
    *   Shards data across multiple Redis nodes. Provides scalability and some degree of fault tolerance (can tolerate some nodes failing).
    *   More complex to manage than Sentinel.

### Framework Behavior During Redis Outage

*   The system will be non-operational. Workers and the API server should implement retry logic with backoff for Redis connections.
*   Upon Redis restoration (either from persistence or via Sentinel/Cluster failover), components should be able to reconnect and resume operations. There might be some stale data or inconsistencies if the outage was prolonged and tasks timed out without the monitor being able to requeue them (because Redis was down).

## 6. Data Integrity for Wordlist Chunks

*   **At-Least-Once Processing:** The design primarily ensures at-least-once processing for wordlist chunks. If a worker fails mid-chunk, or if a task is timed out and requeued, that chunk will be processed again from the beginning by another worker.
*   **No Partial Chunk Assumption:** The `perform_attempt` logic within a worker should not assume any partial completion of a chunk from a previous failed attempt. Each time a worker receives a chunk, it processes it in its entirety.
*   **Fine-Grained Checkpointing (Complexity):** Implementing checkpointing *within* a chunk (e.g., saving progress every N words) would add significant complexity to both worker logic and Redis state management. It's generally avoided unless individual word processing is extremely time-consuming and chunk sizes are very large. The current model relies on chunks being reasonably sized units of work.
*   **Result Duplication:** As mentioned, if a chunk is processed multiple times and results are found, those results might be reported multiple times. The system component that consumes/displays results (e.g., the API server or a downstream client) should be prepared to handle or deduplicate such entries if necessary (e.g., by using a Set for `list:results:<job_id>` or by post-processing).
