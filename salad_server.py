import asyncio
import os
import time
import uuid
from typing import Any

import urllib.request
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from handler import handler


class RunRequest(BaseModel):
    input: dict[str, Any]


app = FastAPI(title="InfiniteTalk Salad API")
_job_lock = asyncio.Lock()
_jobs: dict[str, dict[str, Any]] = {}


def _check_token(authorization: str | None) -> None:
    token = os.getenv("SALAD_API_TOKEN")
    if not token:
        return
    if authorization != f"Bearer {token}":
        raise HTTPException(status_code=401, detail="Unauthorized")


def _comfy_ready() -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8188/", timeout=2) as response:
            return response.status < 500
    except Exception:
        return False


@app.get("/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, str]:
    if not _comfy_ready():
        raise HTTPException(status_code=503, detail="ComfyUI is not ready")
    return {"status": "ready"}


@app.post("/run")
async def run(request: RunRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _check_token(authorization)
    if not _comfy_ready():
        raise HTTPException(status_code=503, detail="ComfyUI is not ready")

    if _job_lock.locked():
        raise HTTPException(status_code=409, detail="Another generation is already running")

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "id": job_id,
        "status": "queued",
        "created_at": time.time(),
        "started_at": None,
        "completed_at": None,
        "result": None,
        "error": None,
    }
    asyncio.create_task(_run_job(job_id, request.input))
    return {"id": job_id, "status": "queued"}


@app.get("/status/{job_id}")
async def status(job_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _check_token(authorization)
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


async def _run_job(job_id: str, job_input: dict[str, Any]) -> None:
    async with _job_lock:
        job = _jobs[job_id]
        job["status"] = "running"
        job["started_at"] = time.time()
        try:
            result = await asyncio.to_thread(handler, {"input": job_input})
            job["completed_at"] = time.time()
            job["result"] = result
            job["status"] = "failed" if isinstance(result, dict) and result.get("error") else "completed"
            if job["status"] == "failed":
                job["error"] = result.get("error")
        except Exception as exc:
            job["completed_at"] = time.time()
            job["status"] = "failed"
            job["error"] = str(exc)
