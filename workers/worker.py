import redis
import time
import json
import os # Not strictly used in this version, but often useful
from workers.config import worker_settings
# Assuming these common functions are adapted to take connection params directly
# or are refactored to not depend on app.config
from common.redis_client import get_redis_connection as get_base_redis_connection
from common.storage_clients import get_s3_client as get_base_s3_client, get_wordlist_chunk_from_s3

# Global Redis and S3 client instances for the worker
r_conn: Optional[redis.Redis] = None # Added Optional type hint
s3_conn: Optional[Any] = None # Added Optional type hint, Any for S3 client

def init_clients():
    global r_conn, s3_conn
    print(f"Worker {worker_settings.WORKER_ID}: Initializing clients...")
    if r_conn is None:
        # This assumes get_base_redis_connection can accept host/port or uses its own config
        # For this implementation, let's assume it's adapted.
        # If common.redis_client.get_redis_connection is a singleton using app.config,
        # this worker would need its own direct redis.Redis instantiation.
        # Based on the prompt's import alias, we assume it can be parameterized or is fine.
        # For now, we'll call it as if it's a direct call that can be configured.
        # A better approach for common.redis_client:
        # def get_redis_connection(host, port, db=0, decode_responses=True):
        #     return redis.Redis(host=host, port=port, db=db, decode_responses=decode_responses)
        try:
            r_conn = redis.Redis(
                host=worker_settings.REDIS_HOST, 
                port=worker_settings.REDIS_PORT, 
                db=0, 
                decode_responses=True
            )
            r_conn.ping() # Verify connection
            print(f"Worker {worker_settings.WORKER_ID}: Successfully connected to Redis at {worker_settings.REDIS_HOST}:{worker_settings.REDIS_PORT}")
        except redis.exceptions.ConnectionError as e:
            print(f"Worker {worker_settings.WORKER_ID}: FATAL - Could not connect to Redis: {e}. Exiting.")
            raise # Re-raise to stop worker if Redis is unavailable at startup

    if s3_conn is None and worker_settings.MINIO_ENDPOINT:
        # Similar assumption for get_base_s3_client or direct instantiation.
        # For now, using direct instantiation based on worker_settings
        # from common.storage_clients import get_s3_client needs to be compatible
        try:
            s3_conn = get_base_s3_client( # This function must be able to take these params
                endpoint_url=worker_settings.MINIO_ENDPOINT,
                access_key=worker_settings.MINIO_ACCESS_KEY,
                secret_key=worker_settings.MINIO_SECRET_KEY,
                use_ssl=worker_settings.MINIO_USE_SSL
            )
            # Add a simple check if possible, e.g., list buckets (if permissions allow)
            # s3_conn.list_buckets() # This is a boto3 method, might vary by client library
            print(f"Worker {worker_settings.WORKER_ID}: Successfully initialized S3 client for endpoint {worker_settings.MINIO_ENDPOINT}")
        except Exception as e:
            print(f"Worker {worker_settings.WORKER_ID}: FATAL - Could not initialize S3 client: {e}. Exiting.")
            raise # Re-raise to stop worker if S3 is unavailable at startup


# Placeholder - this would contain the actual brute-force attempt logic
def perform_attempt(word: str, target_info: dict) -> bool:
    # print(f"Worker {worker_settings.WORKER_ID}: Attempting word '{word}' for target '{target_info.get('url', 'N/A')}'")
    # Simulate work by checking for a specific "secret" in additional_params
    # This is a simple placeholder for actual brute-force logic
    if "secret_password_to_find" in target_info.get("additional_params", {}):
        return word == target_info["additional_params"]["secret_password_to_find"]
    # Default behavior if no secret is defined for the test
    # To make it testable, let's assume a generic secret if not specified
    return word == "password123" # Generic fallback if not in target_info

def process_task(task_details_json: str):
    global r_conn, s3_conn # Ensure global clients are used
    
    try:
        task_details = json.loads(task_details_json)

        job_id = task_details["job_id"]
        chunk_id = task_details["chunk_id"]
        start_line = task_details["start_line"]
        end_line = task_details["end_line"]
        wordlist_bucket = task_details["wordlist_bucket"]
        wordlist_key = task_details["wordlist_key"]

        print(f"Worker {worker_settings.WORKER_ID}: Processing chunk {chunk_id} for job {job_id} (Lines: {start_line}-{end_line}) from {wordlist_bucket}/{wordlist_key}")

        target_info_json_str = r_conn.hget(f"job:{job_id}", "target_info_json_str")
        if not target_info_json_str:
            print(f"Worker {worker_settings.WORKER_ID}: ERROR - No target_info_json_str found for job {job_id}. Marking chunk {chunk_id} as failed.")
            r_conn.hincrby(f"job_stats:{job_id}", "chunks_failed", 1)
            return

        target_info = json.loads(target_info_json_str)
        
        words = get_wordlist_chunk_from_s3(s3_conn, wordlist_bucket, wordlist_key, start_line, end_line)

        for word in words:
            if perform_attempt(word, target_info):
                result_message = json.dumps({
                    "word": word,
                    "chunk_id": chunk_id,
                    "job_id": job_id,
                    "worker_id": worker_settings.WORKER_ID,
                    "timestamp": time.time()
                })
                r_conn.lpush(f"list:results:{job_id}", result_message)
                r_conn.hincrby(f"job_stats:{job_id}", "results_found", 1)
                print(f"Worker {worker_settings.WORKER_ID}: SUCCESS! Found match: '{word}' for job {job_id} in chunk {chunk_id}")
        
        print(f"Worker {worker_settings.WORKER_ID}: Finished processing chunk {chunk_id} for job {job_id}. Words processed: {len(words)}")

    except Exception as e:
        print(f"Worker {worker_settings.WORKER_ID}: ERROR processing chunk {task_details.get('chunk_id', 'N/A')} for job {task_details.get('job_id', 'N/A')}: {e}")
        if 'job_id' in task_details: # Ensure job_id is available to update stats
            r_conn.hincrby(f"job_stats:{task_details['job_id']}", "chunks_failed", 1)
        # Depending on the error, might need more sophisticated handling (e.g., requeue)

def main():
    try:
        init_clients() # Initialize connections when worker starts
    except Exception as e:
        # init_clients now raises exceptions on critical failures
        # No need to print here as init_clients already does.
        return # Stop worker execution

    if not worker_settings.TARGET_JOB_ID:
        print(f"Worker {worker_settings.WORKER_ID}: ERROR - TARGET_JOB_ID not set in environment or .env file. Exiting.")
        return

    target_job_id = worker_settings.TARGET_JOB_ID
    task_queue_key = f"queue:tasks:{target_job_id}"
    job_stats_key = f"job_stats:{target_job_id}"
    inprogress_set_key = f"zset:inprogress:{target_job_id}"

    print(f"Worker {worker_settings.WORKER_ID} started successfully.")
    print(f"Listening for tasks on queue: {task_queue_key}")
    print(f"Monitoring job status from Redis key: {job_stats_key}")

    try:
        while True:
            current_job_status = r_conn.hget(job_stats_key, "status")
            if current_job_status == "PAUSED":
                print(f"Worker {worker_settings.WORKER_ID}: Job {target_job_id} is PAUSED. Sleeping for {worker_settings.TASK_POLL_TIMEOUT}s...")
                time.sleep(worker_settings.TASK_POLL_TIMEOUT)
                continue
            if current_job_status in ["COMPLETED", "FAILED"]: # Using "COMPLETED" as per JobDefinition status values
                 print(f"Worker {worker_settings.WORKER_ID}: Job {target_job_id} is {current_job_status}. Worker exiting.")
                 break

            task_data_tuple = r_conn.brpop([task_queue_key], timeout=worker_settings.TASK_POLL_TIMEOUT)

            if task_data_tuple:
                _queue_name, task_json = task_data_tuple 
                try:
                    task_details = json.loads(task_json)
                    chunk_id = task_details.get("chunk_id", f"unknown_chunk_{uuid.uuid4()}") # Ensure chunk_id is always available
                except json.JSONDecodeError:
                    print(f"Worker {worker_settings.WORKER_ID}: ERROR - Could not decode task JSON: {task_json}")
                    # Potentially move to a dead-letter queue
                    continue

                print(f"Worker {worker_settings.WORKER_ID}: Received task for chunk {chunk_id} from {_queue_name}")
                
                r_conn.zadd(inprogress_set_key, {chunk_id: time.time()})
                
                process_task(task_json) 
                
                r_conn.hincrby(job_stats_key, "chunks_processed", 1)
                r_conn.hset(job_stats_key, "last_update_timestamp", time.time()) # Update last processed time
                r_conn.zrem(inprogress_set_key, chunk_id)
            else:
                # print(f"Worker {worker_settings.WORKER_ID}: No task received from {task_queue_key} after {worker_settings.TASK_POLL_TIMEOUT}s timeout.")
                pass # Loop again after timeout

    except KeyboardInterrupt:
        print(f"Worker {worker_settings.WORKER_ID}: SIGINT received. Shutting down gracefully...")
    except redis.exceptions.ConnectionError as e:
        print(f"Worker {worker_settings.WORKER_ID}: Redis connection error: {e}. Shutting down.")
    except Exception as e:
        print(f"Worker {worker_settings.WORKER_ID}: An unexpected error occurred in main loop: {e}. Shutting down.")
    finally:
        # Potential cleanup tasks, though Python handles most on exit
        print(f"Worker {worker_settings.WORKER_ID}: Stopped.")

if __name__ == "__main__":
    # For type hinting, though not strictly necessary for runtime
    from typing import Optional, Any 
    import uuid # For fallback chunk_id

    main()
