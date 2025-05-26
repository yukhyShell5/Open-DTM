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

The following steps are a *conceptual guide* on how one might set up and run the implemented version of this framework. **Note: No code is currently implemented.**

### Prerequisites:

*   Python 3.8+
*   Redis server (running and accessible)
*   MinIO server (or other S3-compatible object storage, running and accessible)
*   `pip` (Python package installer)
*   `git` (for cloning the repository)

### Installation (Conceptual):

1.  **Clone the repository (if it were implemented):**
    ```bash
    git clone https://github.com/yourusername/educational-bruteforce-framework.git # Replace with actual URL if hosted
    cd educational-bruteforce-framework
    ```

2.  **Create and activate a virtual environment (recommended):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies (conceptual `requirements.txt`):**
    A `requirements.txt` file would be created with necessary packages like:
    ```
    fastapi
    uvicorn[standard]
    redis
    boto3 # For S3/MinIO
    pydantic
    # ... other necessary libraries
    ```
    Installation command:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up Environment Variables:**
    An `.env.example` file would be provided (see `docs/project_structure_and_snippets.md`). Copy it to `.env` and fill in your specific configurations (Redis host/port, MinIO access keys, etc.).
    ```bash
    cp .env.example .env
    # Edit .env with your settings
    ```

### Running Redis and MinIO:

*   Ensure your Redis server is running and accessible based on your `.env` configuration.
*   Ensure your MinIO (or other S3) server is running, accessible, and configured with buckets for wordlists.

### Running the API Server (Conceptual):

1.  Navigate to the API server directory (based on `docs/project_structure_and_snippets.md`):
    ```bash
    cd bruteforce_framework/app 
    ```
2.  Start the FastAPI application using Uvicorn:
    ```bash
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
    ```
    The API server would then be accessible, e.g., at `http://localhost:8000/docs` for the OpenAPI documentation.

### Running Worker Nodes (Conceptual):

1.  Navigate to the worker directory:
    ```bash
    cd bruteforce_framework/workers
    ```
2.  Start one or more worker instances. Workers would need configuration (via `.env` or command-line arguments) to connect to Redis and storage.
    A worker might be started to listen for tasks from any job or be targeted:
    ```bash
    python worker.py 
    # Or, if designed to target specific jobs initially:
    # python worker.py --job-id <specific_job_id_from_api>
    ```
    Multiple instances of `worker.py` could be run on different machines or in different terminals, each connecting to the same Redis and storage backend.

### Submitting a Job (Conceptual):

Jobs would be submitted by making an HTTP POST request to the API server's `/api/v1/jobs` endpoint. This could be done using tools like `curl`, Postman, or a custom client script.

Example using `curl` (refer to `docs/api_design.md` for the actual JSON payload structure):
```bash
curl -X POST "http://localhost:8000/api/v1/jobs" \
     -H "Content-Type: application/json" \
     -d '{
           "target_info": { "url": "http://example.com/login", "username_field": "user", "password_field": "pass" },
           "wordlist_storage_type": "s3",
           "wordlist_path": "s3://mybucket/wordlists/common_passwords.txt",
           "chunk_strategy": { "type": "LINE_BASED", "size": 10000 }
         }'
```
The API would respond with a `job_id`, which can then be used to monitor status, pause/resume, or retrieve results.

## 6. Contributing (Placeholder)

This project currently exists as a set of design documents. Should this project move towards an actual implementation, contributions would be welcome! Standard open-source practices would apply:

1.  Fork the repository.
2.  Create a new branch for your feature or bug fix.
3.  Make your changes.
4.  Submit a pull request with a clear description of your contributions.

Discussions on design improvements or implementation strategies are also encouraged via Issues.

## 7. License

This project is licensed under the **MIT License**.
(A `LICENSE` file would be included in the root directory with the full text of the MIT License if this were a coded project.)
```
