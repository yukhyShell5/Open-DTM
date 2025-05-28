from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Dict, Optional, List, Deque
import uuid
import time
import asyncio
from collections import deque
import logging
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montage des fichiers statiques et templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("task-manager")

# Structures de données
tasks_db: Dict[str, Dict] = {}
available_workers: Deque[str] = deque()
worker_tasks: Dict[str, str] = {}  # worker_id -> task_id
worker_last_seen: Dict[str, float] = {}
pending_worker_requests: Dict[str, asyncio.Future] = {}
worker_status: Dict[str, str] = {}  # idle, busy

class Task(BaseModel):
    id: str
    command: str
    status: str = "pending"  # pending, processing, completed, failed
    result: Optional[str] = None
    worker_id: Optional[str] = None
    created_at: float = time.time()
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

class WorkerRequest(BaseModel):
    worker_id: str

class ResultSubmission(BaseModel):
    result: str
    worker_id: str
    success: bool = True

# Endpoints
@app.post("/submit_task")
async def submit_task(command: str):
    task_id = str(uuid.uuid4())
    task = Task(
        id=task_id, 
        command=command
    )
    tasks_db[task_id] = task.dict()
    logger.info(f"Task submitted: {task_id} - {command[:50]}...")
    
    # Si des workers sont disponibles, on leur envoie immédiatement
    if available_workers:
        worker_id = available_workers.popleft()
        if worker_id in pending_worker_requests:
            future = pending_worker_requests.pop(worker_id)
            if not future.done():
                task_data = tasks_db[task_id]
                task_data["status"] = "processing"
                task_data["worker_id"] = worker_id
                task_data["started_at"] = time.time()
                worker_tasks[worker_id] = task_id
                worker_status[worker_id] = "busy"
                future.set_result(task_data)
                logger.info(f"Task {task_id} immediately assigned to worker {worker_id}")
    
    return {"task_id": task_id}

# Nouvel endpoint pour les heartbeats
@app.post("/heartbeat/{worker_id}")
async def receive_heartbeat(worker_id: str):
    worker_last_seen[worker_id] = time.time()
    # Ne pas modifier le statut du worker ici
    return {"status": "alive"}

@app.post("/worker_available")
async def worker_available(request: WorkerRequest):
    worker_id = request.worker_id
    worker_last_seen[worker_id] = time.time()  # Mise à jour du dernier contact
    
    # Vérifier s'il y a des tâches immédiatement disponibles
    for task_id, task in tasks_db.items():
        if task["status"] == "pending":
            task["status"] = "processing"
            task["worker_id"] = worker_id
            task["started_at"] = time.time()
            worker_tasks[worker_id] = task_id
            worker_status[worker_id] = "busy"
            logger.info(f"Task {task_id} assigned to worker {worker_id}")
            return task
    
    # Si aucune tâche disponible, on garde la requête en attente
    future = asyncio.Future()
    pending_worker_requests[worker_id] = future
    available_workers.append(worker_id)
    worker_status[worker_id] = "idle"
    logger.debug(f"Worker {worker_id} added to available queue")
    
    try:
        # Attendre maximum 30s avant de timeout
        task = await asyncio.wait_for(future, timeout=30.0)
        return task
    except asyncio.TimeoutError:
        # Retirer le worker de la liste d'attente
        if worker_id in pending_worker_requests:
            del pending_worker_requests[worker_id]
        if worker_id in available_workers:
            available_workers.remove(worker_id)
        logger.debug(f"Worker {worker_id} timed out waiting for task")
        return {"status": "no_task"}

@app.post("/submit_result/{task_id}")
async def submit_result(task_id: str, result: ResultSubmission):
    if task_id in tasks_db:
        tasks_db[task_id]["result"] = result.result
        tasks_db[task_id]["status"] = "completed" if result.success else "failed"
        tasks_db[task_id]["completed_at"] = time.time()
        
        # Libérer le worker
        worker_id = result.worker_id
        if worker_id in worker_tasks:
            del worker_tasks[worker_id]
        if worker_id in worker_status:
            worker_status[worker_id] = "idle"
        logger.info(f"Task {task_id} completed by worker {worker_id}")
    
    return {"status": "success"}

@app.get("/tasks")
async def get_tasks():
    return list(tasks_db.values())

@app.get("/workers")
async def get_workers():
    workers = []
    for worker_id, last_seen in worker_last_seen.items():
        workers.append({
            "id": worker_id,
            "status": worker_status.get(worker_id, "unknown"),
            "last_seen": last_seen,
            "current_task": worker_tasks.get(worker_id)
        })
    return workers

@app.get("/stats")
async def get_stats():
    stats = {
        "total_tasks": len(tasks_db),
        "pending_tasks": sum(1 for t in tasks_db.values() if t["status"] == "pending"),
        "processing_tasks": sum(1 for t in tasks_db.values() if t["status"] == "processing"),
        "completed_tasks": sum(1 for t in tasks_db.values() if t["status"] == "completed"),
        "failed_tasks": sum(1 for t in tasks_db.values() if t["status"] == "failed"),
        "total_workers": len(worker_last_seen),
        "idle_workers": sum(1 for s in worker_status.values() if s == "idle"),
        "busy_workers": sum(1 for s in worker_status.values() if s == "busy"),
    }
    # Garantir que toutes les clés existent même avec valeur 0
    for key in ['total_tasks', 'pending_tasks', 'processing_tasks', 'completed_tasks', 
                'failed_tasks', 'total_workers', 'idle_workers', 'busy_workers']:
        if key not in stats:
            stats[key] = 0
    return stats

# Nettoyage des workers inactifs
async def worker_cleanup():
    while True:
        await asyncio.sleep(10)
        current_time = time.time()
        dead_workers = []
        
        for worker_id, last_seen in list(worker_last_seen.items()):
            if current_time - last_seen > 30:  # 30s sans activité
                dead_workers.append(worker_id)
                if worker_id in worker_tasks:
                    task_id = worker_tasks[worker_id]
                    if tasks_db[task_id]["status"] == "processing":
                        tasks_db[task_id]["status"] = "pending"
                        tasks_db[task_id]["worker_id"] = None
                        del worker_tasks[worker_id]
                logger.warning(f"Worker {worker_id} marked as dead")
        
        for worker_id in dead_workers:
            if worker_id in worker_last_seen:
                del worker_last_seen[worker_id]
            if worker_id in worker_status:
                del worker_status[worker_id]
            if worker_id in available_workers:
                available_workers.remove(worker_id)
            if worker_id in pending_worker_requests:
                if not pending_worker_requests[worker_id].done():
                    pending_worker_requests[worker_id].set_result({"status": "no_task"})
                del pending_worker_requests[worker_id]

# Endpoint pour l'interface web
@app.get("/")
async def dashboard(request: Request):
    tasks = list(tasks_db.values())
    workers = await get_workers()
    stats = await get_stats()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "tasks": tasks,
            "workers": workers,
            "stats": stats
        }
    )

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(worker_cleanup())
    logger.info("Task Manager started")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)