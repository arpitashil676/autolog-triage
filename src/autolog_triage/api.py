"""FastAPI service exposing the triage pipeline.

Run with::

    uvicorn autolog_triage.api:app --reload

Endpoints
---------
* ``GET  /health``  -- liveness + active LLM provider.
* ``POST /triage``  -- submit raw log text, get a structured report as JSON.

FastAPI/pydantic are optional; importing this module without them raises a
clear error, while the rest of the package (CLI, pipeline) keeps working.
"""

from __future__ import annotations

import json
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "FastAPI is required for the API. Install with: pip install fastapi uvicorn pydantic"
    ) from exc

from .agents.llm import get_provider
from .agents.orchestrator import TriageOrchestrator
from .data.parser import parse_line

app = FastAPI(title="AutoLog Triage", version="0.1.0")


class TriageRequest(BaseModel):
    run_id: str = "adhoc"
    log_text: str


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "provider": getattr(get_provider(), "name", "unknown"),
        "time": datetime.utcnow().isoformat(),
    }


@app.post("/triage")
def triage(req: TriageRequest) -> JSONResponse:
    entries = [parse_line(i, ln) for i, ln in enumerate(req.log_text.splitlines(), start=1) if ln.strip()]
    orch = TriageOrchestrator()
    report = orch.run(run_id=req.run_id, source_file="api://inline", entries=entries)
    return JSONResponse(content=json.loads(report.to_json()))
