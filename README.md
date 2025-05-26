# Educational Distributed Brute-Force Framework

## ⚠️ Ethical Use Notice ⚠️

**This project is designed and intended STRICTLY for educational and research purposes ONLY.**

Its goal is to serve as a learning tool for understanding distributed systems architecture. **Under no circumstances should this framework, its concepts, or any derived code be used for malicious activities, unauthorized access, or any illegal purposes.**

Please read the [**Ethical Use Guidelines (`docs/ETHICAL_USE.md`)**](./docs/ETHICAL_USE.md) carefully before reviewing any other part of this project. By examining or using any part of this project, you agree to adhere to these ethical principles and take full responsibility for your actions.

## 1. Introduction/Overview

This project outlines the design for a **Distributed Brute-Force Framework**, a system conceptualized to handle long-running, potentially high-latency brute-force tasks by distributing the workload across multiple worker nodes.

Key features of the designed framework include:
*   **Task Chunking:** Breaking down large wordlists into manageable chunks.
*   **Dynamic Dispatch:** Workers pull tasks from a central queue.
*   **Resumable & Fault-Tolerant Execution:** Mechanisms to handle worker failures and allow jobs to be paused and resumed.
*   **Redis as Task Broker:** Leveraging Redis for managing task queues, job states, and results.
*   **External Wordlist Storage:** Storing large wordlists in scalable systems like S3-compatible object storage.

The primary educational goal is to provide a platform for learning about distributed systems architecture, task management, inter-component communication, and fault tolerance in such systems. This is a **design-only project**; no functional code for actual brute-force operations is provided or intended.

## 2. Architecture Overview

The framework is designed around several key components that work together to distribute and process tasks:

*   **API Server (FastAPI):** The central control point. It receives job submissions from clients, interacts with Redis to manage job metadata and task queues, and provides endpoints for status monitoring and control.
*   **Worker Nodes:** These are the computational units that execute the brute-force tasks. They fetch tasks from Redis, retrieve wordlist chunks from external storage, perform the (simulated) processing, and report results and progress back to Redis.
*   **Redis:** Acts as a high-speed message broker, task queue manager, and state store. It holds job definitions, pending tasks, in-progress task tracking, and results.
*   **External Wordlist Storage (S3-compatible):** Large wordlists are stored in an external system like MinIO or AWS S3, from which workers fetch specific chunks.

For a detailed explanation of the architecture, components, and data flow, please refer to:
**[Detailed Architecture Document (`docs/architecture.md`)](./docs/architecture.md)**

### Simplified Architecture Diagram:

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

## 3. Core Technologies (Conceptual)

The design of this framework leverages the following core technologies:

*   **Python 3.x:** As the primary programming language.
*   **FastAPI:** For building the efficient and modern API server.
*   **Redis:** As the in-memory data store for task queues, job metadata, and state management.
*   **S3-Compatible Object Storage:** Such as MinIO (self-hosted) or cloud services (AWS S3, Google Cloud Storage) for storing large wordlist files.
*   **Pydantic:** For data validation and settings management within FastAPI and other components.

## 4. Design Documents

This project is primarily a collection of design documents that detail its architecture and operational logic. These can be found in the `docs/` directory:

*   **`docs/ETHICAL_USE.md`**: **Crucial Read.** Ethical guidelines and responsible use of this educational project.
*   **`docs/architecture.md`**: Provides a high-level overview of the system architecture, components, and data flow between them.
*   **`docs/redis_structures.md`**: Details the specific Redis data structures used for managing jobs, tasks, status, and results.
*   **`docs/wordlist_management.md`**: Explains how wordlists are stored, accessed, and chunked for distributed processing.
*   **`docs/worker_logic.md`**: Describes the operational logic of the worker nodes, including task fetching, processing, and error handling.
*   **`docs/fault_tolerance.md`**: Outlines the mechanisms designed for fault tolerance and job resumability (e.g., handling worker failures, job pausing/resuming).
*   **`docs/api_design.md`**: Specifies the FastAPI interface, including endpoints for job submission, status checks, control, and result retrieval.
*   **`docs/project_structure_and_snippets.md`**: Proposes a potential directory structure for implementing the project and includes conceptual Python code snippets for key functionalities.

## 5. Conceptual Setup and Running (Illustrative)

The following sections describe how one might build, configure, and run the system if it were fully implemented, primarily using Docker Compose.

### Building and Running with Docker Compose

This is the recommended way to run the system for a development or testing environment.

**Prerequisites:**
*   Docker installed and running.
*   Docker Compose installed.

**Steps:**

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/yourusername/educational-bruteforce-framework.git # Replace with actual URL if hosted
    cd educational-bruteforce-framework
    ```

2.  **Create and Customize `.env` File:**
    Copy the example environment file and customize it if needed.
    ```bash
    cp .env.example .env
    ```
    Review `.env` and set variables like `TARGET_JOB_ID` for each worker instance you intend to run (if not scaling via Docker Compose initially, or if you want specific workers on specific jobs). For MinIO, the default credentials `minioadmin/minioadmin` are used in `docker-compose.yml`. If you change them there, update your S3 client configurations accordingly.

3.  **Build and Start Services:**
    Run the following command from the project root directory:
    ```bash
    docker-compose up --build -d
    ```
    This command will:
    *   Build the Docker images for the `api_server`, `worker`, and `monitor` services as defined in their respective Dockerfiles.
    *   Start all services defined in `docker-compose.yml` (Redis, MinIO, API Server, Worker(s), Monitor) in detached mode (`-d`).

4.  **Checking Logs:**
    To view the logs for specific services:
    ```bash
    docker-compose logs api_server
    docker-compose logs worker
    docker-compose logs monitor
    # Use -f to follow logs: docker-compose logs -f api_server
    ```

5.  **Stopping Services:**
    To stop all running services:
    ```bash
    docker-compose down
    # To remove volumes as well (e.g., Redis data, MinIO data):
    # docker-compose down -v
    ```

6.  **Scaling Workers (Example):**
    After the initial `docker-compose up`, you can scale the number of worker instances:
    ```bash
    docker-compose up --scale worker=3 -d
    ```
    This command will ensure three instances of the `worker` service are running. Note that each worker instance will need its `TARGET_JOB_ID` configured, typically via environment variables in the `docker-compose.yml` or by updating the `.env` file if the `env_file` directive is used per service. For multiple workers targeting the *same* job, this is fine. For workers targeting *different* jobs, you would define multiple worker services in `docker-compose.yml` with different environment variable settings for `TARGET_JOB_ID`.

### Configuration

The services within this framework (API Server, Worker, Monitor) are configured primarily through **environment variables**.

*   **`.env.example`**: This file in the project root provides a template and description of common environment variables. It's crucial for understanding available settings.
*   **Pydantic Settings Files**: Each service has a Python configuration module that uses Pydantic's `BaseSettings` to load these environment variables:
    *   API Server: `app/config.py` (loads `Settings`)
    *   Worker: `workers/config.py` (loads `WorkerSettings`)
    *   Monitor: `scripts/config_monitor.py` (loads `MonitorSettings`)
*   **Docker Compose Overrides**: When running via `docker-compose.yml`, environment variables set directly in the `environment:` section for each service will take precedence over defaults in the Python settings files. If an `.env` file is explicitly loaded by a service in `docker-compose.yml` via `env_file:`, those values can also influence the configuration.

Key variables to be aware of:
*   `REDIS_HOST`, `REDIS_PORT`: For connecting to Redis.
*   `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`: For MinIO/S3 connection.
*   `TARGET_JOB_ID` (for workers): Specifies which job queue a worker instance should listen to. This is essential for worker operation.
*   Monitor-specific settings like `STALE_TASK_TIMEOUT_SECONDS`, `MONITOR_POLL_INTERVAL_SECONDS`.

### Interacting with the System (Conceptual)

Once the system is running (e.g., via `docker-compose up`), you can interact with it through its API.

1.  **Prepare Wordlist in MinIO:**
    The API server and workers expect wordlists to be in an S3-compatible object store (MinIO by default in Docker Compose).
    *   Access MinIO console: `http://localhost:9001` (default credentials: `minioadmin/minioadmin`).
    *   The `wordlists` bucket is created automatically by the MinIO service in `docker-compose.yml`.
    *   Upload your wordlist file (e.g., `sample.txt`) into the `wordlists` bucket.
    *   Alternatively, use the MinIO Client (`mc`):
        ```bash
        # 1. Install mc: https://min.io/docs/minio/linux/reference/minio-mc.html#install-mc
        # 2. Alias your local MinIO:
        mc alias set myminio http://localhost:9000 minioadmin minioadmin
        # 3. Create a sample wordlist file:
        echo -e "password123\ntestword\nsecret" > sample.txt
        # 4. Copy to the 'wordlists' bucket (which should be auto-created):
        mc cp sample.txt myminio/wordlists/sample.txt
        ```

2.  **Submit a Job:**
    Use a tool like `curl` or Postman to send a POST request to the `/api/v1/jobs` endpoint.
    ```bash
    # Ensure wordlists/sample.txt exists in your MinIO 'wordlists' bucket
    curl -X POST "http://localhost:8000/api/v1/jobs" \
    -H "Content-Type: application/json" \
    -d '{
      "target_info": {
        "url": "http://example.com/login", 
        "service_type": "http_post_form",
        "additional_params": {"secret_password_to_find": "password123"} 
      },
      "wordlist_storage_type": "minio",
      "wordlist_path": "wordlists/sample.txt", 
      "chunk_strategy": {
        "type": "LINE_BASED",
        "size": 100 
      }
    }'
    ```
    *   The `target_info.additional_params.secret_password_to_find` is used by the current placeholder `perform_attempt` logic in `workers/worker.py`.
    *   The API should respond with a JSON object containing the `job_id`. Note this `job_id`.

3.  **Configure and Start Workers for the Job:**
    *   Edit your `.env` file (or `docker-compose.yml` if you prefer to manage it there).
    *   Set the `TARGET_JOB_ID` variable to the `job_id` you received from the API.
        Example in `.env`: `TARGET_JOB_ID=your_job_id_here`
    *   If `docker-compose.yml` for the worker service uses `env_file: .env`, these changes will be picked up when workers (re)start.
    *   If workers are already running, you might need to restart them to pick up the new `TARGET_JOB_ID` unless they are designed to dynamically query for available jobs (which the current basic worker is not).
        ```bash
        docker-compose restart worker 
        # Or if scaling:
        # docker-compose up --scale worker=1 -d # (Adjust scale as needed)
        ```

4.  **Check Job Status:**
    Use the `job_id` to query the job's status:
    ```bash
    curl "http://localhost:8000/api/v1/jobs/your_job_id_here"
    ```

5.  **Get Job Results:**
    Once the job has processed some chunks and found results (based on the placeholder `perform_attempt`):
    ```bash
    curl "http://localhost:8000/api/v1/jobs/your_job_id_here/results"
    ```

## 6. Project Structure Overview

The project is organized into the following main directories:

*   **`app/`**: Contains the FastAPI API server application.
    *   `api/`: Defines the API endpoints (e.g., job submission, status).
    *   `core/`: Core business logic for job management and wordlist processing.
    *   `config.py`: Pydantic settings for the API server.
    *   `main.py`: FastAPI application entry point.
*   **`workers/`**: Contains the worker node application.
    *   `worker.py`: Main script for worker logic (task fetching, processing).
    *   `config.py`: Pydantic settings for workers.
    *   `target_connectors/`: (Conceptual) For different brute-force target types.
*   **`common/`**: Shared utilities, e.g., Redis and S3 client initializers.
*   **`scripts/`**: Standalone scripts, such as the `monitor.py` for handling stale tasks.
*   **`docs/`**: All design and architecture markdown documents.
*   **`docker-compose.yml`**: Defines services for running the entire stack (Redis, MinIO, API server, workers, monitor).
*   **`Dockerfile`s**: Located in `app/`, `workers/`, and `scripts/` for building container images.

## 7. Contributing (Placeholder)

This project currently exists as a set of design documents and basic structural code. Should this project move towards a more complete implementation, contributions would be welcome! Standard open-source practices would apply:

1.  Fork the repository.
2.  Create a new branch for your feature or bug fix.
3.  Make your changes.
4.  Submit a pull request with a clear description of your contributions.

Discussions on design improvements or implementation strategies are also encouraged via Issues.

## 8. License

This project is licensed under the **MIT License**.
(A `LICENSE` file would be included in the root directory with the full text of the MIT License if this were a coded project.)
