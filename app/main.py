from fastapi import FastAPI

app = FastAPI(title="Distributed Brute-Force Framework API")

@app.get("/")
def main():
    return 'Hello sur la page de Distributed Brute-Force Framework'

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}

# Placeholder for API v1 router
# from app.api.v1 import jobs_router # Example if you had a jobs_router
# app.include_router(jobs_router, prefix="/api/v1")
