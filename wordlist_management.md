# Wordlist Management in Distributed Brute-Force Framework

This document details the strategies for storing, accessing, and chunking wordlists within the distributed brute-force framework. Effective wordlist management is crucial for handling potentially massive datasets and enabling efficient parallel processing.

## 1. External Wordlist Storage

### Rationale

Wordlists used in brute-force attacks can range from small custom lists to multi-gigabyte or even terabyte-sized collections. Storing such large files directly in Redis is impractical and goes against its design as an in-memory data store. Redis is optimized for speed and managing smaller pieces of data like job metadata and task queues, not bulk file storage. Therefore, wordlists must be hosted on an external storage system designed for large data.

### Recommended Solutions

Two primary types of external storage are recommended:

#### Object Storage (S3-compatible)

*   **Examples:** MinIO (self-hosted), AWS S3, Google Cloud Storage, Azure Blob Storage.
*   **Advantages:**
    *   **Scalability:** Object storage systems are designed to scale to handle vast amounts of data with high durability.
    *   **Durability:** Typically offer built-in data replication and redundancy.
    *   **HTTP-based Access:** Wordlist chunks can be fetched by workers using standard HTTP `GET` requests, often with support for `Range` headers to retrieve specific portions of a file. This simplifies access for workers, which might be geographically distributed or running in containerized environments.
    *   **Decoupling:** Keeps wordlist storage separate from the compute infrastructure, allowing each to scale independently.
*   **Considerations:** Data transfer costs (especially with cloud providers) if workers are in different regions than the storage.

#### Network File System (NFS)

*   **Use Cases:** Suitable if the API server and all worker nodes are located within a trusted network (e.g., a single data center or a well-connected VPC) where shared file system mounts can be reliably configured.
*   **Advantages:**
    *   Can be simpler to set up in existing on-premises environments.
    *   File access is transparent to the worker once the NFS share is mounted.
*   **Complexities:**
    *   **Scalability:** NFS can become a bottleneck if not designed for high-throughput, concurrent access from many clients.
    *   **Access Management:** Managing permissions and ensuring consistent mounts across a large, dynamic fleet of workers can be complex.
    *   **Resilience:** The NFS server itself can be a single point of failure if not set up in a high-availability configuration.

### Access Control

Regardless of the chosen storage solution, secure access to wordlists is paramount.
*   **Object Storage:** Typically managed via IAM roles, access keys, and bucket policies. Workers need credentials or instance profiles that grant read-only access to the specific wordlist buckets/objects.
*   **NFS:** Managed through standard POSIX permissions, network ACLs, and Kerberos.
These credentials and permissions must be securely distributed and managed for the worker nodes.

## 2. Wordlist Preparation and Upload

### Wordlist Format

The framework primarily expects wordlists to be:
*   **Plain text files.**
*   Each potential password/phrase on a **new line** (i.e., line-delimited).
*   Common encodings like UTF-8 are preferred.

Binary files or wordlists in proprietary formats are not directly supported without pre-conversion.

### User Process

1.  **Preparation:** The user prepares their wordlist file according to the expected format. This might involve unzipping archives, converting from other formats, or curating specific lists.
2.  **Upload to External Storage:**
    *   The user uploads the prepared wordlist file to the chosen external storage system.
        *   **Object Storage Example:** Using the MinIO client (`mc cp mywordlist.txt s3alias/mybucket/wordlists/mywordlist.txt`) or AWS CLI (`aws s3 cp mywordlist.txt s3://mybucket/wordlists/mywordlist.txt`).
        *   **NFS Example:** Copying the file to the designated directory on the NFS share (`cp mywordlist.txt /mnt/nfs/wordlists/`).
    *   The framework itself (specifically the API server) generally does *not* handle direct file uploads from users for wordlists due to the potential size and the desire to decouple storage. However, a sophisticated UI layer built on top might offer such features, which would then interact with the chosen backend storage.
3.  **Provide Path/URL:** When submitting a brute-force job, the user provides the unique path or URL to the uploaded wordlist.
    *   Example for S3: `s3://mybucket/wordlists/mywordlist.txt`
    *   Example for MinIO (assuming a local alias): `myminio/mybucket/wordlists/mywordlist.txt`
    *   Example for NFS: `/nfs/wordlists/mywordlist.txt`

This path is stored in the `job:<job_id>` hash in Redis (`wordlist_path` field).

## 3. Wordlist Chunking Strategy

### Purpose of Chunking

Chunking the wordlist into smaller, manageable pieces is essential for:
*   **Distributing Work:** Allows different parts of the wordlist to be processed by different worker nodes simultaneously.
*   **Parallel Processing:** Directly enables the parallel nature of the distributed framework.
*   **Resumability & Fault Tolerance:** If a worker fails while processing a chunk, only that specific chunk needs to be rescheduled. Progress is not lost for successfully processed chunks.
*   **Memory Management:** Workers only need to load a small portion of the wordlist into memory at any given time.

### Primary Strategy: Line-Based Chunking

This is the preferred and most straightforward method, given that wordlists are typically line-delimited.

**Process:**

1.  **Obtain Total Line Count:**
    *   When a job is submitted, the API server (or a dedicated pre-processing utility) needs to determine the total number of lines in the specified wordlist.
    *   **Object Storage:** This can be challenging as S3-compatible storage typically doesn't provide line count metadata directly. Options include:
        *   Downloading the file temporarily to count lines (feasible for smaller files).
        *   Using tools like `wc -l` via a streaming download if possible.
        *   For very large files, this might be an expensive operation. An estimation based on file size and average line length could be used, or the user might be required to provide the line count.
        *   Some systems might allow running a serverless function (e.g., AWS Lambda) on the storage to count lines upon upload.
    *   **NFS:** A simple `wc -l /path/to/wordlist.txt` can get the line count.
    *   This `total_lines` value is important for calculating progress.

2.  **Define Chunk Size:**
    *   A `chunk_size` (number of lines per chunk) is defined as a parameter when submitting the job (e.g., 10,000 lines). This value is stored in `job:<job_id>::chunk_size`.
    *   The `chunk_definition_type` in `job:<job_id>` is set to `LINE_BASED`.

3.  **Calculate Number of Chunks:**
    *   `total_chunks = ceil(total_lines / chunk_size)`
    *   This `total_chunks` value is stored in `job:<job_id>::total_chunks`.

4.  **Determine Chunk Boundaries:**
    *   For each chunk `i` (from 0 to `total_chunks - 1`):
        *   `start_line = i * chunk_size`
        *   `end_line = (i + 1) * chunk_size - 1`
        *   Adjust `end_line` for the last chunk: `end_line = min(end_line, total_lines - 1)`.

5.  **Populate Task Queue:**
    *   For each calculated chunk, a task message is created. This message includes:
        *   `chunk_id`: A unique identifier (e.g., `job_id + "_" + chunk_index`).
        *   `job_id`: The ID of the parent job.
        *   `chunk_index`: The sequential index of this chunk.
        *   `start_specifier`: The `start_line` (0-indexed).
        *   `end_specifier`: The `end_line`.
    *   These task messages (as JSON strings) are pushed into the `queue:tasks:<job_id>` Redis list. (Example: `{"chunk_id": "job1_chunk_5", "job_id": "job1", "chunk_index": 5, "start_line": 40001, "end_line": 50000}`)

### Alternative Strategy: Byte-Range Chunking (Briefly Mention)

*   **Concept:** Instead of line numbers, workers are assigned a byte `start_offset` and `end_offset` within the wordlist file.
*   **Use Cases:**
    *   When line counting is prohibitively expensive for extremely large files.
    *   For binary files or data that is not strictly line-oriented (though less common for traditional wordlists).
*   **Complexities:**
    *   **Partial Words:** A worker fetching a byte range might receive partial words at the beginning or end of its chunk. Logic must be implemented to handle this:
        *   The worker might need to discard the first partial line if `start_offset > 0` and it doesn't start at a newline character.
        *   The worker might need to read slightly beyond its `end_offset` to complete the last partial line (or coordinate with the next chunk's worker, which is complex).
    *   This adds complexity to worker logic and may require careful coordination to ensure no words are missed or processed twice.
    *   The `chunk_definition_type` in `job:<job_id>` would be set to `BYTE_RANGE`.

### Worker Responsibility

1.  **Receive Task:** A worker fetches a task message from `queue:tasks:<job_id>`. This message contains `start_line` and `end_line` (for line-based chunking) or `start_offset` and `end_offset` (for byte-range chunking).
2.  **Fetch Assigned Portion:**
    *   **Object Storage (S3):** The worker uses an S3 client library. For line-based chunking, it might still need to fetch a larger portion and then select lines, or if the storage and client library support it efficiently, iterate through the file lines and skip to the `start_line`, processing until `end_line`. For byte-range chunking, it uses HTTP `Range` requests (e.g., `Range: bytes=start_offset-end_offset`) to download only its assigned segment of the file.
    *   **NFS:** The worker opens the file, seeks to the appropriate `start_line` (by reading and discarding lines) or `start_offset` (using file seek operations), and then reads lines/bytes until `end_line` or `end_offset` is reached.
3.  **Process Chunk:** The worker then processes the words within its assigned chunk.

## 4. Considerations for Chunking

### Chunk Size

The choice of `chunk_size` involves a trade-off:
*   **Smaller Chunks:**
    *   **Pros:** Better load balancing across workers, quicker redistribution of work if a worker fails (smaller recovery unit).
    *   **Cons:** Higher overhead due to more tasks, more frequent interactions with Redis and the wordlist storage system (potentially more API calls for object storage).
*   **Larger Chunks:**
    *   **Pros:** Lower overhead per word, fewer tasks to manage.
    *   **Cons:** Can lead to poorer load balancing if chunk processing times vary significantly. If a worker fails with a large chunk, more processing time is lost and must be redone.

The optimal chunk size may depend on the average wordlist size, the number of workers, and the performance characteristics of the storage and network. It should be a configurable job parameter.

### Metadata

The API server or the job creation utility is responsible for calculating and storing key metadata related to chunking in the `job:<job_id>` Redis hash:
*   `total_chunks`: Essential for the API server to track overall job progress (e.g., "X out of Y chunks processed").
*   `chunk_definition_type`: (`LINE_BASED` or `BYTE_RANGE`)
*   `chunk_size`: (lines or bytes)

This metadata allows the system to understand the job's structure and how progress should be interpreted.
