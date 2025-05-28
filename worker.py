import asyncio
import time
import subprocess
import uuid
import logging
import signal
import aiohttp
import os

# Configuration
MANAGER_URL = os.getenv("MANAGER_URL", "http://localhost:8000")
HEARTBEAT_INTERVAL = 5  # secondes
WORKER_ID = str(uuid.uuid4())

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(f"worker-{WORKER_ID[:8]}")

# Gestion du shutdown
shutdown_flag = False

def signal_handler(sig, frame):
    global shutdown_flag
    logger.info("Shutdown signal received")
    shutdown_flag = True

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

async def process_task(task, session):
    try:
        logger.info(f"Processing task {task['id']}: {task['command']}")
        
        process = subprocess.Popen(
            ['/bin/bash', '-c', task["command"]],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        result_lines = []
        last_heartbeat = time.time()
        
        while True:
            if time.time() - last_heartbeat > 3:
                try:
                    await session.post(
                        f"{MANAGER_URL}/heartbeat/{WORKER_ID}",
                        timeout=3
                    )
                    last_heartbeat = time.time()
                except Exception:
                    pass
            
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
                
            if output:
                result_lines.append(output.strip())
            
            await asyncio.sleep(0.1)
        
        return_code = process.wait()
        result = "\n".join(result_lines)
        
        return (result, True) if return_code == 0 else (f"Command failed with code {return_code}\n{result}", False)
            
    except subprocess.CalledProcessError as e:
        logger.error(f"Task {task['id']} failed: {str(e)}")
        return (f"Command failed with error: {str(e)}", False)
    except Exception as e:
        logger.error(f"Unexpected error in task processing: {str(e)}")
        return (f"Unexpected error: {str(e)}", False)

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
            logger.debug("Heartbeat timed out (normal)")
        except aiohttp.ClientError as e:
            logger.warning(f"Heartbeat failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in heartbeat: {str(e)}")
        
        await asyncio.sleep(HEARTBEAT_INTERVAL)

async def main_loop(session):
    while not shutdown_flag:
        try:
            # Signaler la disponibilité
            async with session.post(
                f"{MANAGER_URL}/worker_available",
                json={"worker_id": WORKER_ID},
                timeout=30
            ) as response:
                if response.status != 200:
                    await asyncio.sleep(5)
                    continue
                    
                data = await response.json()
                if "id" not in data:
                    await asyncio.sleep(1)
                    continue
                
                # Traitement de la tâche
                task = data
                result, success = await process_task(task, session)
                
                # Soumettre le résultat
                try:
                    async with session.post(
                        f"{MANAGER_URL}/submit_result/{task['id']}",
                        json={
                            "result": result,
                            "worker_id": WORKER_ID,
                            "success": success
                        },
                        timeout=10
                    ) as response:
                        if response.status != 200:
                            logger.error(f"Failed to submit result for task {task['id']}")
                except Exception as e:
                    logger.error(f"Result submission failed: {str(e)}")
                    
        except asyncio.TimeoutError:
            logger.debug("Worker available request timed out (normal)")
            await asyncio.sleep(5)
        except aiohttp.ClientError as e:
            logger.error(f"Connection error: {str(e)}")
            await asyncio.sleep(10)
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            await asyncio.sleep(10)

async def main():
    # Configuration de la session HTTP avec timeout par défaut
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        heartbeat_task = asyncio.create_task(send_heartbeat(session))
        main_task = asyncio.create_task(main_loop(session))
        
        try:
            await asyncio.gather(heartbeat_task, main_task)
        except asyncio.CancelledError:
            logger.info("Shutting down gracefully...")
        except Exception as e:
            logger.error(f"Fatal error: {str(e)}")

if __name__ == "__main__":
    print(f"Starting worker {WORKER_ID}")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        shutdown_flag = True
        logger.info("Worker shutdown complete")