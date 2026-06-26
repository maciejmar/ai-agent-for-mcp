from __future__ import annotations

import os
from threading import Lock
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent import stream_diagnostics
from mcp_tools import MCPTools


class DiagnosticRequest(BaseModel):
    log_path: str | None = None


mcp_tools = MCPTools.from_env()


app = FastAPI(title="Isolated Network Diagnostic Agent", version="0.1.0")
cors_origins = [
    origin.strip()
    for origin in os.getenv("BACKEND_CORS_ORIGINS", "http://localhost:4200,http://127.0.0.1:4200").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

latest_lock = Lock()
latest_result: dict[str, Any] = {
    "graph_status": "idle",
    "current_step": "idle",
    "steps": [],
    "findings": [],
    "recommendations": [],
    "llm_status": "idle",
    "llm_summary": "",
}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/graph/status")
def graph_status() -> dict[str, Any]:
    with latest_lock:
        return {
            "graph_status": latest_result.get("graph_status", "idle"),
            "current_step": latest_result.get("current_step", "idle"),
            "steps": latest_result.get("steps", []),
        }


@app.get("/diagnostics/latest")
def diagnostics_latest() -> dict[str, Any]:
    with latest_lock:
        return dict(latest_result)


@app.get("/llm/inference-status")
def llm_inference_status() -> dict[str, Any]:
    return mcp_tools.get_llm_inference_status()


@app.post("/diagnostics/run")
def diagnostics_run(request: DiagnosticRequest) -> dict[str, Any]:
    global latest_result

    log_path = request.log_path
    if log_path and not (log_path.startswith("/") or log_path.startswith("docker://")):
        log_path = None

    final_state: dict[str, Any] = {}
    for state in stream_diagnostics(log_path):
        final_state = dict(state)
        with latest_lock:
            latest_result = final_state

    return final_state
