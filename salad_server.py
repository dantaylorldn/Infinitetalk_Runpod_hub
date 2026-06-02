import asyncio
import os
from typing import Any

import urllib.request
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from handler import handler


class RunRequest(BaseModel):
    input: dict[str, Any]


app = FastAPI(title="InfiniteTalk Salad API")
_job_lock = asyncio.Lock()


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

    async with _job_lock:
        return await asyncio.to_thread(handler, {"input": request.input})
