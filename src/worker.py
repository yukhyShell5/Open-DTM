import asyncio
import time
# import subprocess # Non utilisé pour l'exécution de tâche, gardé pour référence
import uuid
import logging
import signal
import aiohttp
import os
import docker

# Configuration
MANAGER_URL = os.getenv("MANAGER_URL", "http://localhost:8000")
HEARTBEAT_INTERVAL = 5  # secondes
WORKER_ID = str(uuid.uuid4())
DEFAULT_DOCKER_IMAGE = os.getenv("DEFAULT_DOCKER_IMAGE", "alpine/git")
DOCKER_TASK_TIMEOUT = int(os.getenv("DOCKER_TASK_TIMEOUT", "300"))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(f"worker-{WORKER_ID[:8]}")

shutdown_flag = False

def signal_handler(sig, frame):
    global shutdown_flag
    logger.info("Shutdown signal received")
    shutdown_flag = True

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# --- NOUVELLE FONCTION UTILITAIRE ---
def parse_image_name_and_tag(image_full_name: str) -> tuple[str, str]:
    """Sépare un nom d'image complet en nom de dépôt et tag."""
    image_name = image_full_name
    tag = "latest" # Tag par défaut si non spécifié
    if ':' in image_full_name:
        parts = image_full_name.rsplit(':', 1)
        # Gérer le cas où le ':' fait partie du nom du registre (ex: localhost:5000/image)
        # Une heuristique simple: si la partie après le dernier ':' ne contient pas de '/', c'est un tag.
        if '/' not in parts[1]:
            image_name = parts[0]
            tag = parts[1]
        # Sinon, c'est que le nom complet est le nom de l'image et le tag est 'latest' implicitement.
        # ex: "myregistry.com:5000/my/image" -> image_name="myregistry.com:5000/my/image", tag="latest"

    # Gérer les digests (ex: image@sha256:digest)
    if '@' in image_name: # Si le @ est dans le nom de base
        base_name, digest_part = image_name.split('@', 1)
        # Si on avait un tag spécifié et un digest, le tag est ignoré par Docker
        # Pour client.images.pull, on peut passer 'image@digest' comme 'repository' et tag=None implicitement
        # ou 'image' comme repository et 'digest' comme tag.
        # Pour simplifier, si un digest est présent, on considère que c'est le "tag" effectif.
        tag = digest_part # En réalité, pour pull, on passerait repo=base_name, tag=digest_part ou juste repo=image_name
        image_name = base_name

    return image_name, tag
# --- FIN NOUVELLE FONCTION UTILITAIRE ---

async def process_task(task: dict):
    task_id = task['id']
    command_to_run = task["command"]
    # Permet à la tâche de spécifier sa propre image Docker, sinon utilise la valeur par défaut
    image_to_use_full_name = task.get("docker_image", DEFAULT_DOCKER_IMAGE)
    
    logger.info(f"Processing task {task_id} via Docker (image: {image_to_use_full_name}): {command_to_run[:100]}...")

    docker_client = None
    try:
        docker_client = await asyncio.to_thread(docker.from_env)
        await asyncio.to_thread(docker_client.ping)
    except docker.errors.DockerException as e:
        logger.error(f"Task {task_id}: Docker not available or not responding: {e}")
        return (f"Docker not available on worker: {str(e)}", False)
    except Exception as e:
        logger.error(f"Task {task_id}: Failed to initialize Docker client: {e}")
        return (f"Failed to initialize Docker client: {str(e)}", False)

    shell_command = ["/bin/sh", "-c", command_to_run]
    container_name = f"dtm-task-{task_id}-{WORKER_ID[:8]}-{uuid.uuid4().hex[:6]}"
    container = None
    
    image_pull_attempted_for_this_task = False 

    while True: 
        try:
            logger.debug(f"Task {task_id}: Attempting to create container '{container_name}' with image '{image_to_use_full_name}'")
            container = await asyncio.to_thread(
                docker_client.containers.create,
                image=image_to_use_full_name,
                command=shell_command,
                name=container_name,
                detach=True,
                cap_drop=['ALL'],
                mem_limit="256m",
            )
            break 

        except docker.errors.ImageNotFound:
            if image_pull_attempted_for_this_task:
                logger.error(f"Task {task_id}: Image '{image_to_use_full_name}' still not found after pull attempt.")
                return (f"Docker image '{image_to_use_full_name}' not found even after pull attempt.", False)

            logger.warning(f"Task {task_id}: Docker image '{image_to_use_full_name}' not found locally.")
            
            user_choice = 'n' # Par défaut, ne pas puller si non interactif
            try:
                prompt_message = f"Image '{image_to_use_full_name}' not found. Attempt to pull it? (y/n): "
                user_choice = await asyncio.to_thread(input, prompt_message)
            except RuntimeError as e: 
                logger.warning(f"Cannot prompt user for image pull (stdin not a tty?): {e}. Will not attempt pull for {image_to_use_full_name}.")
                return (f"Docker image '{image_to_use_full_name}' not found, and cannot prompt for pull.", False)


            if user_choice.lower().strip() == 'y':
                image_pull_attempted_for_this_task = True 
                logger.info(f"Attempting to pull image '{image_to_use_full_name}'...")
                try:
                    repo_name, tag_name = parse_image_name_and_tag(image_to_use_full_name)
                    logger.debug(f"Pulling: repository='{repo_name}', tag='{tag_name}'")
                    
                    pull_stream = await asyncio.to_thread(docker_client.api.pull, repository=repo_name, tag=tag_name, stream=True, decode=True)
                    
                    for chunk in pull_stream:
                        status = chunk.get('status')
                        progress = chunk.get('progress')
                        error_detail = chunk.get('errorDetail') # Docker envoie 'errorDetail' et 'error'
                        error_message = chunk.get('error')

                        if error_detail or error_message:
                            err_msg = error_detail.get('message', error_message) if error_detail else error_message
                            logger.error(f"Error pulling image '{image_to_use_full_name}': {err_msg}")
                            return (f"Failed to pull Docker image '{image_to_use_full_name}': {err_msg}", False)
                        
                        if status:
                            log_line = f"Pulling {repo_name}:{tag_name} - {status}"
                            if progress:
                                log_line += f" ({progress})"
                            logger.info(log_line)
                    
                    logger.info(f"Image '{image_to_use_full_name}' pulled successfully. Retrying container creation.")
                    continue 
                except docker.errors.APIError as pull_err:
                    logger.error(f"Failed to pull image '{image_to_use_full_name}': {pull_err}")
                    return (f"Failed to pull Docker image '{image_to_use_full_name}': {pull_err}", False)
                except Exception as e_pull: 
                    logger.error(f"Unexpected error during image pull of '{image_to_use_full_name}': {e_pull}", exc_info=True)
                    return (f"Unexpected error pulling Docker image '{image_to_use_full_name}': {str(e_pull)}", False)
            else:
                logger.info(f"User declined to pull the image '{image_to_use_full_name}' or prompt failed.")
                return (f"User declined to pull missing Docker image '{image_to_use_full_name}'.", False)
        
        except docker.errors.APIError as e:
            logger.error(f"Task {task_id}: Docker API error during container creation: {e}")
            return (f"Docker API error during container creation: {str(e)}", False)
        
        except Exception as e_create: 
            logger.error(f"Task {task_id}: Unexpected error during container creation: {e_create}", exc_info=True)
            return (f"Unexpected error during container creation: {str(e_create)}", False)

    try:
        logger.info(f"Task {task_id}: Starting container {container.short_id} ({container_name})")
        await asyncio.to_thread(container.start)

        result_info = await asyncio.wait_for(
            asyncio.to_thread(container.wait), 
            timeout=DOCKER_TASK_TIMEOUT
        )
        exit_code = result_info.get("StatusCode", -1)

        stdout_bytes = await asyncio.to_thread(container.logs, stdout=True, stderr=False, timestamps=False)
        stderr_bytes = await asyncio.to_thread(container.logs, stdout=False, stderr=True, timestamps=False)
        
        stdout_str = stdout_bytes.decode('utf-8', errors='replace').strip()
        stderr_str = stderr_bytes.decode('utf-8', errors='replace').strip()

        if exit_code == 0:
            logger.info(f"Task {task_id} (container {container.short_id}) completed successfully (exit code 0).")
            return (stdout_str if stdout_str else "Command executed successfully with no output.", True)
        else:
            full_log_output = f"Task {task_id} (container {container.short_id}) failed with exit code {exit_code}.\n"
            if stdout_str: full_log_output += f"--- STDOUT ---\n{stdout_str}\n"
            if stderr_str: full_log_output += f"--- STDERR ---\n{stderr_str}\n"
            full_log_output += "--- END LOGS ---"
            logger.error(full_log_output)
            result_to_return = stderr_str if stderr_str else stdout_str
            if not result_to_return: result_to_return = f"Command failed with exit code {exit_code}."
            return (result_to_return, False)

    except asyncio.TimeoutError:
        logger.error(f"Task {task_id} (container {container.short_id if container else 'N/A'}) timed out after {DOCKER_TASK_TIMEOUT}s.")
        if container:
            logger.info(f"Attempting to stop timed out container {container.short_id}...")
            try:
                await asyncio.to_thread(container.stop, timeout=10)
            except docker.errors.APIError as stop_err:
                logger.warning(f"Could not stop container {container.short_id} gracefully: {stop_err}. Attempting to kill.")
                try: await asyncio.to_thread(container.kill)
                except docker.errors.APIError as kill_err: logger.error(f"Could not kill container {container.short_id}: {kill_err}")
            except Exception as e_stop_kill: logger.error(f"Error during stop/kill of container {container.short_id}: {e_stop_kill}")
        return (f"Task execution timed out after {DOCKER_TASK_TIMEOUT} seconds in Docker.", False)
    
    except docker.errors.APIError as e:
        logger.error(f"Task {task_id} (container {container.short_id if container else 'N/A'}): Docker API error: {e}")
        return (f"Docker API error: {str(e)}", False)
        
    except Exception as e:
        logger.error(f"Task {task_id} (container {container.short_id if container else 'N/A'}): Unexpected error in Docker task processing: {e}", exc_info=True)
        return (f"Unexpected error during Docker execution: {str(e)}", False)
    
    finally:
        if container:
            try:
                logger.debug(f"Task {task_id}: Attempting to remove container {container.short_id} ({container_name})...")
                await asyncio.to_thread(container.remove, v=True)
                logger.info(f"Task {task_id}: Container {container.short_id} removed.")
            except docker.errors.NotFound:
                logger.debug(f"Task {task_id}: Container {container.short_id} already removed or not found.")
            except docker.errors.APIError as e:
                logger.warning(f"Task {task_id}: Could not remove container {container.short_id}: {str(e)}")
            except Exception as e_remove:
                logger.error(f"Task {task_id}: Error removing container {container.short_id}: {e_remove}")


async def send_heartbeat(session):
    while not shutdown_flag:
        try:
            async with session.post(
                f"{MANAGER_URL}/heartbeat/{WORKER_ID}",
                timeout=3
            ) as response:
                if response.status != 200:
                    logger.warning(f"Heartbeat failed with status {response.status}")
        except asyncio.TimeoutError:
            logger.debug("Heartbeat POST request timed out (normal if manager is slow/busy)")
        except aiohttp.ClientError as e:
            logger.warning(f"Heartbeat failed due to client error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in send_heartbeat: {str(e)}", exc_info=True)
        await asyncio.sleep(HEARTBEAT_INTERVAL)

async def main_loop(session):
    while not shutdown_flag:
        try:
            logger.info("Signaling availability to manager...")
            async with session.post(
                f"{MANAGER_URL}/worker_available",
                json={"worker_id": WORKER_ID},
                timeout=aiohttp.ClientTimeout(total=35.0)
            ) as response:
                if response.status != 200:
                    logger.warning(f"Failed to signal availability or manager returned error: {response.status}")
                    await asyncio.sleep(5)
                    continue
                    
                task_data = await response.json()
                if "id" not in task_data or "command" not in task_data:
                    if task_data.get("status") == "no_task":
                        logger.info("No task available from manager, waiting...")
                    else:
                        logger.warning(f"Received invalid task data from manager: {task_data}")
                    await asyncio.sleep(1)
                    continue
                
                result, success = await process_task(task_data) 
                
                logger.info(f"Submitting result for task {task_data['id']}...")
                try:
                    async with session.post(
                        f"{MANAGER_URL}/submit_result/{task_data['id']}",
                        json={"result": str(result), "worker_id": WORKER_ID, "success": success},
                        timeout=10
                    ) as result_response:
                        if result_response.status != 200:
                            logger.error(f"Failed to submit result for task {task_data['id']}: HTTP {result_response.status}")
                        else:
                            logger.info(f"Result for task {task_data['id']} submitted successfully.")
                except Exception as e_submit:
                    logger.error(f"Result submission for task {task_data['id']} failed: {str(e_submit)}", exc_info=True)
                    
        except asyncio.TimeoutError:
            logger.info("Worker available request to manager timed out (normal, will retry).")
        except aiohttp.ClientConnectorError as e:
            logger.error(f"Connection error with manager at {MANAGER_URL}: {str(e)}. Retrying in 10s...")
            await asyncio.sleep(10)
        except aiohttp.ClientError as e:
            logger.error(f"AIOHTTP client error: {str(e)}. Retrying in 10s...")
            await asyncio.sleep(10)
        except Exception as e:
            logger.error(f"Unexpected error in main_loop: {str(e)}", exc_info=True)
            await asyncio.sleep(10)

async def main():
    http_timeout = aiohttp.ClientTimeout(total=None, connect=10, sock_read=30, sock_connect=10)
    async with aiohttp.ClientSession(timeout=http_timeout) as session:
        logger.info(f"Worker {WORKER_ID} starting...")
        logger.info(f"Manager URL: {MANAGER_URL}")
        logger.info(f"Default Docker image: {DEFAULT_DOCKER_IMAGE}")
        logger.info(f"Docker task timeout: {DOCKER_TASK_TIMEOUT}s")

        heartbeat_bg_task = asyncio.create_task(send_heartbeat(session))
        main_worker_loop_task = asyncio.create_task(main_loop(session))
        
        done, pending = await asyncio.wait(
            [heartbeat_bg_task, main_worker_loop_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task_to_cancel in pending:
            task_to_cancel.cancel()

        await asyncio.gather(*pending, return_exceptions=True)
        logger.info(f"Worker {WORKER_ID} shutting down.")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info(f"Worker {WORKER_ID} received KeyboardInterrupt, initiating shutdown...")
    finally:
        logger.info(f"Worker {WORKER_ID} has shut down.")