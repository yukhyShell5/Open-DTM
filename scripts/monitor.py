import redis
import time
import json # Not used in this version, but good to have if task details were richer
from scripts.config_monitor import monitor_settings
# Assuming common.redis_client provides a basic connection function
# If not, define a local one or adjust common.redis_client.
# For this subtask, let's assume a simple local redis connection setup.

def get_redis_conn(host, port):
    return redis.Redis(host=host, port=port, db=0, decode_responses=True)

def requeue_stale_tasks(r_conn: redis.Redis): # Added type hint for r_conn
    print(f"Monitor: Scanning for jobs with pattern '{monitor_settings.JOB_ID_PATTERN}'...")
    # Find all job definition keys (e.g., "job:uuid-...")
    # Using scan_iter for potentially large number of keys
    job_keys = list(r_conn.scan_iter(match=monitor_settings.JOB_ID_PATTERN))
    
    if not job_keys:
        print("Monitor: No active job definitions found to monitor based on pattern.")
        return

    for job_key in job_keys:
        try:
            job_id_parts = job_key.split(":", 1)
            if len(job_id_parts) < 2:
                print(f"Monitor: Invalid job key format found: {job_key}. Skipping.")
                continue
            job_id = job_id_parts[1]
        except Exception as e:
            print(f"Monitor: Error processing job key {job_key}: {e}. Skipping.")
            continue
            
        # Check job status - only monitor RUNNING jobs
        job_stats_key = f"job_stats:{job_id}"
        job_status = r_conn.hget(job_stats_key, "status")
        
        if job_status != "RUNNING":
            # This can be verbose if many non-running jobs exist, so commented out for now
            # print(f"Monitor: Job {job_id} is not RUNNING (status: {job_status}). Skipping.")
            continue

        print(f"Monitor: Checking job {job_id} for stale tasks...")
        inprogress_set_key = f"zset:inprogress:{job_id}"
        # task_queue_key = f"queue:tasks:{job_id}" # Needed if actual requeueing task messages

        stale_threshold_time = time.time() - monitor_settings.STALE_TASK_TIMEOUT_SECONDS
        
        stale_tasks_with_scores = r_conn.zrangebyscore(inprogress_set_key, 0, stale_threshold_time, withscores=True)

        if not stale_tasks_with_scores:
            print(f"Monitor: No stale tasks found for job {job_id}.")
            continue

        for chunk_id_bytes, score in stale_tasks_with_scores:
            chunk_id = chunk_id_bytes # Already decoded due to decode_responses=True in Redis client

            # **Design Limitation Note for Requeueing:**
            # To properly requeue, the monitor needs the full original task message, 
            # not just the chunk_id. The current design of `zset:inprogress:{job_id}` 
            # only stores `chunk_id`s. A robust solution would store the full task message 
            # (e.g., as JSON) in the ZSET member, or in a separate Redis hash keyed by `chunk_id`.
            # For this educational example, we will log this limitation and simulate by
            # removing the task from in-progress and incrementing a counter.
            # The task itself is effectively "lost" if the worker processing it has died.

            print(f"Monitor: Stale task {chunk_id} (started at epoch {score:.0f}) in job {job_id}. Simulating requeue due to timeout.")
            
            if r_conn.zrem(inprogress_set_key, chunk_id):
                print(f"Monitor: Removed stale task {chunk_id} from {inprogress_set_key} for job {job_id}.")
                # Increment a counter for monitoring purposes
                r_conn.hincrby(job_stats_key, "chunks_stale_removed_by_monitor", 1)
                
                # If actual requeueing were possible with full task message:
                # original_task_message_json = ... # Fetch or reconstruct this
                # r_conn.lpush(task_queue_key, original_task_message_json)
                # print(f"Monitor: Task {chunk_id} (simulated actual requeue) pushed to {task_queue_key}.")
            else:
                # This case should be rare if logic is correct, means task was removed between ZRANGEBYSCORE and ZREM
                print(f"Monitor: Stale task {chunk_id} was already removed from {inprogress_set_key} (job {job_id}) before this monitor instance could act.")


def main():
    print("Starting Stale Task Monitor...")
    try:
        r_conn = get_redis_conn(monitor_settings.REDIS_HOST, monitor_settings.REDIS_PORT)
        r_conn.ping()
        print(f"Monitor connected to Redis at {monitor_settings.REDIS_HOST}:{monitor_settings.REDIS_PORT}.")
    except redis.exceptions.ConnectionError as e:
        print(f"Monitor: FATAL - Could not connect to Redis: {e}. Exiting.")
        return
    except Exception as e:
        print(f"Monitor: FATAL - Error during Redis connection or initial ping: {e}. Exiting.")
        return

    try:
        while True:
            print(f"Monitor: Starting new scan cycle at {time.strftime('%Y-%m-%d %H:%M:%S')}")
            requeue_stale_tasks(r_conn)
            print(f"Monitor: Scan cycle complete. Sleeping for {monitor_settings.MONITOR_POLL_INTERVAL_SECONDS} seconds...")
            time.sleep(monitor_settings.MONITOR_POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("Monitor: SIGINT received. Shutting down...")
    except Exception as e:
        print(f"Monitor: An unexpected error occurred in the main loop: {e}")
    finally:
        if 'r_conn' in locals() and r_conn:
            try:
                r_conn.close()
                print("Monitor: Redis connection closed.")
            except Exception as e:
                print(f"Monitor: Error closing Redis connection: {e}")
        print("Monitor: Finished.")

if __name__ == "__main__":
    main()
