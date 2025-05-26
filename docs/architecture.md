# Distributed Brute-Force Framework Architecture

## 1. Introduction

The purpose of this framework is to provide an educational platform for understanding and experimenting with distributed brute-force techniques. It allows users to submit target hashes and wordlists, distributing the cracking process across multiple worker nodes to accelerate the search for a matching password. This document outlines the high-level architecture and data flow of the system.

## 2. Components

The framework consists of the following key components:

### 2.1. Client/User Interface

Users interact with the framework primarily through a **Command-Line Interface (CLI)** tool. This CLI allows users to:
*   Submit new brute-force jobs (specifying target hash, hash type, and wordlist location).
*   Check the status of ongoing or completed jobs.
*   Pause, resume, or cancel jobs.
*   Retrieve results for completed jobs.

Alternatively, a web-based interface could be provided by the API Server (FastAPI) for a more visual interaction, but the core functionality is exposed via the CLI.

### 2.2. API Server (FastAPI)

The API Server, built using FastAPI, acts as the central control point for the entire framework. Its responsibilities include:
*   Receiving job submissions from clients.
*   Validating job parameters.
*   Interacting with Redis to create and manage job metadata and task queues.
*   Providing endpoints for clients to query job status, progress, and results.
*   Handling commands to pause, resume, or cancel jobs, and propagating these commands via Redis.

The API server is stateless wherever possible, relying on Redis to store persistent job information.

### 2.3. Task Queue (Redis)

Redis serves as a high-speed message broker and task queue manager. It is **not** used for storing large data like wordlists or comprehensive results. Key Redis data structures and their uses include:
*   **Pending Tasks Queue (List):** A list for each job, storing chunks of the wordlist that need to be processed. Workers poll this queue.
*   **Job Metadata (Hashes):** Stores information about each job, such as target hash, hash type, wordlist location, status (e.g., pending, running, paused, completed, failed), submission time, etc.
*   **Progress Tracking (Hashes/Counters):** Stores the number of chunks processed, estimated time remaining, etc., for each job.
*   **Worker Heartbeats (Sorted Sets/Hashes):** To keep track of active workers and their current status.
*   **Command Channels (Pub/Sub):** Used to broadcast commands like pause/resume to workers.

Redis's speed is crucial for efficiently dispatching tasks and updating statuses.

### 2.4. Worker Nodes

Worker nodes are responsible for the actual brute-force computation. Each worker:
*   Polls Redis for available tasks from the pending tasks queue for active jobs.
*   Upon receiving a task (which specifies a wordlist chunk and target hash), fetches the corresponding chunk of the wordlist directly from Wordlist Storage.
*   Executes the brute-force logic (hashing words from the chunk and comparing them against the target hash).
*   Reports progress (e.g., number of passwords tried) back to Redis periodically.
*   Reports successful outcomes (found passwords) immediately to Result Storage (and/or Redis).
*   Listens for control commands (e.g., pause, resume) via Redis Pub/Sub.

Workers are designed to be scalable and resilient; new workers can be added to increase processing power, and the system should tolerate worker failures.

### 2.5. Wordlist Storage

Large wordlists are stored in an external, scalable storage solution. This is critical because wordlists can be gigabytes or even terabytes in size and are not suitable for storage in Redis. Options include:
*   **Object Storage:** MinIO (self-hosted) or cloud-based services like AWS S3, Google Cloud Storage.
*   **Shared Network File System (NFS):** If workers have access to a common file system.

Workers fetch specific chunks (ranges of lines/bytes) of the wordlist directly from this storage based on the task assigned to them. The API server might pre-process the wordlist to determine chunk boundaries or this could be done by workers dynamically.

### 2.6. Result Storage

Successfully cracked passwords and associated job information need to be stored. Options include:
*   **Redis (Initially):** For simplicity in the initial implementation, found passwords can be stored in a Redis list or hash associated with the job ID. This allows the API server to quickly retrieve results for the client.
*   **Dedicated Database:** For more robust and scalable storage, a relational database (e.g., PostgreSQL, MySQL) or a NoSQL database (e.g., MongoDB) could be used. This would allow for better querying and management of results over time.
*   **Files:** Results could also be written to files in a designated storage location, perhaps organized by job ID.

The choice depends on the desired durability, query capabilities, and complexity. For an educational tool, Redis might suffice initially.

## 3. Architecture Diagram (ASCII Art)

```
+-----------------+      +---------------------+      +-------------------+
| Client/User     |<---->| API Server (FastAPI)|<---->| Task Queue (Redis)|
| (CLI / Web UI)  |      +---------------------+      +-------------------+
+-----------------+               ^      ^                      |   ^
                                  |      | (Metadata, Status)   |   | (Commands)
                                  |      |                      |   |
                                  |      +----------------------V---+
                                  | (Results)             (Tasks, Progress)
                                  |                             |
                                  |                             v
+-----------------+      +--------V----------+      +-------------------+
| Result Storage  |<-----|   Worker Nodes    |<---->| Wordlist Storage  |
| (Redis/DB/Files)|      | (Multiple Instances)|      | (MinIO, S3, NFS)  |
+-----------------+      +-------------------+      +-------------------+
```

## 4. Data Flow Descriptions

### 4.1. Job Submission

1.  **Client -> API Server:** User submits a job via the CLI (e.g., `brute-force-cli submit --hash <hash> --type <type> --wordlist s3://bucket/list.txt`).
2.  **API Server -> Redis:**
    *   The API server validates the request.
    *   It creates an entry in Redis for job metadata (e.g., job ID, hash, wordlist path, status: "pending").
    *   It may pre-calculate wordlist chunk information or determine the total number of chunks.
    *   It populates the pending tasks queue in Redis with initial tasks (references to wordlist chunks).

### 4.2. Task Dispatching & Processing

1.  **Worker -> Redis:** A worker node, upon starting or completing a previous task, polls the relevant job's pending tasks queue in Redis for a new task.
2.  **Redis -> Worker:** Redis provides a task to the worker (e.g., job ID, wordlist chunk identifier/range).
3.  **Worker -> Wordlist Storage:** The worker uses the task information to fetch the specific chunk of the wordlist directly from the Wordlist Storage (e.g., MinIO, S3).
4.  **Worker (Processing):** The worker iterates through the words in the fetched chunk, hashes them according to the job's hash type, and compares them against the target hash.
5.  **Worker -> Redis (Progress):** Periodically, the worker reports its progress (e.g., number of words processed in the current chunk, overall chunk completion) back to Redis, updating job-specific progress counters.

### 4.3. Progress Updates

1.  **Worker -> Redis:** As described above, workers update progress metrics in Redis (e.g., "job:<id>:progress", "job:<id>:chunks_done").
2.  **API Server -> Redis:** When a client requests a status update, the API server reads this progress information from Redis.
3.  **API Server -> Client:** The API server formats the progress data and sends it back to the client.

### 4.4. Result Reporting

1.  **Worker -> Result Storage/Redis:** If a worker finds a matching password:
    *   It immediately sends the found password and relevant job ID to the designated Result Storage.
    *   This might be directly to a Redis list for found passwords (e.g., "job:<id>:results").
    *   Alternatively, it could write to a database or a file, depending on the configured Result Storage mechanism.
2.  **Worker -> Redis (Status Update):** The worker also updates the job's status in Redis to "completed" (or marks that a password has been found, as a job might continue if configured to find all matches).
3.  **API Server -> Redis (Optional/On-Demand):** The API server can query Redis for results when the client requests them.
4.  **API Server -> Client:** The API server retrieves the found password(s) from Redis or other Result Storage and presents them to the client.

### 4.5. Job Status Query

1.  **Client -> API Server:** User requests the status of a specific job using the CLI (e.g., `brute-force-cli status --job-id <job_id>`).
2.  **API Server -> Redis:** The API server queries Redis for the metadata and current progress information associated with the given job ID.
3.  **Redis -> API Server:** Redis returns the stored data (status, progress, submission time, etc.).
4.  **API Server -> Client:** The API server formats this information and sends it back to the client.

### 4.6. Job Pause/Resume

1.  **Client -> API Server:** User issues a pause or resume command for a job via the CLI (e.g., `brute-force-cli pause --job-id <job_id>`).
2.  **API Server -> Redis:**
    *   The API server updates the job's status in its Redis metadata entry (e.g., to "paused" or "running").
    *   The API server publishes a command message (e.g., "pause_job:<job_id>" or "resume_job:<job_id>") to a specific Redis Pub/Sub channel that active workers are subscribed to.
3.  **Redis -> Workers (via Pub/Sub):** Workers subscribed to the command channel receive the message.
4.  **Workers (Action):**
    *   **On Pause:** Workers processing tasks for the specified job ID will attempt to gracefully stop their current chunk processing (e.g., finish the current word, or stop immediately) and will stop polling for new tasks for that job ID until a resume command is received. They might report their current state before pausing.
    *   **On Resume:** If the job status is updated to "running", workers will resume polling the pending tasks queue for that job and continue processing.
The API server might also directly manipulate the pending task queues (e.g., temporarily moving tasks to a different "paused" queue) if a more robust pause is required, though Pub/Sub is generally sufficient for signaling.
