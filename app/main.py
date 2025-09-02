from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import settings
from .debug_store import store
from .endpoints import stt_ws, health, test, audio_viewer
from .endpoints.tts_ws import ws_tts

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("stt")

app = FastAPI(title="stefan-api-test-16 – STT+TTS-backend (FastAPI + Realtime)")


# ----------------------- CORS -----------------------
origins = []
regex = None
for part in [p.strip() for p in settings.cors_origins.split(",") if p.strip()]:
    if "*" in part:
        # översätt *.lovable.app => regex
        escaped = re.escape(part).replace(r"\*\.", ".*")
        regex = rf"https://{escaped}" if part.startswith("*.") else rf"{escaped}"
    else:
        origins.append(part)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inkludera routers
app.include_router(stt_ws.router, tags=["stt"])
app.include_router(health.router, tags=["health"])
app.include_router(test.router, prefix="/api", tags=["test"])
app.include_router(audio_viewer.router, prefix="/api", tags=["audio"])


# --------------------- Models -----------------------
class ConfigOut(BaseModel):
    realtime_url: str
    transcribe_model: str
    input_language: str
    commit_interval_ms: int
    cors_origins: list[str]
    cors_regex: Optional[str]

class DebugListOut(BaseModel):
    session_id: str
    data: list

# --------------------- Endpoints --------------------

@app.get("/config", response_model=ConfigOut)
async def get_config():
    return ConfigOut(
        realtime_url=settings.realtime_url,
        transcribe_model=settings.transcribe_model,
        input_language=settings.input_language,
        commit_interval_ms=settings.commit_interval_ms,
        cors_origins=origins,
        cors_regex=regex,
    )

@app.get("/debug/frontend-chunks", response_model=DebugListOut)
async def debug_frontend_chunks(session_id: str = Query(...), limit: int = Query(200, ge=1, le=1000)):
    buf = store.get_or_create(session_id)
    data = list(buf.frontend_chunks)[-limit:]
    return DebugListOut(session_id=session_id, data=data)

@app.get("/debug/openai-chunks", response_model=DebugListOut)
async def debug_openai_chunks(session_id: str = Query(...), limit: int = Query(200, ge=1, le=1000)):
    buf = store.get_or_create(session_id)
    data = list(buf.openai_chunks)[-limit:]
    return DebugListOut(session_id=session_id, data=data)

@app.get("/debug/openai-text", response_model=DebugListOut)
async def debug_openai_text(session_id: str = Query(...), limit: int = Query(200, ge=1, le=2000)):
    buf = store.get_or_create(session_id)
    data = list(buf.openai_text)[-limit:]
    return DebugListOut(session_id=session_id, data=data)

@app.get("/debug/frontend-text", response_model=DebugListOut)
async def debug_frontend_text(session_id: str = Query(...), limit: int = Query(200, ge=1, le=2000)):
    buf = store.get_or_create(session_id)
    data = list(buf.frontend_text)[-limit:]
    return DebugListOut(session_id=session_id, data=data)

@app.get("/debug/rt-events", response_model=DebugListOut)
async def debug_rt_events(session_id: str = Query(...), limit: int = Query(200, ge=1, le=2000)):
    buf = store.get_or_create(session_id)
    data = list(buf.rt_events)[-limit:]
    return DebugListOut(session_id=session_id, data=data)

@app.post("/debug/reset")
async def debug_reset(session_id: str | None = Query(None)):
    store.reset(session_id)
    return {"ok": True, "session_id": session_id}

# --------------------- WebSocket --------------------
# WebSocket-hantering flyttad till app/endpoints/stt_ws.py

# TTS WebSocket endpoint
app.websocket("/ws/tts")(ws_tts)


