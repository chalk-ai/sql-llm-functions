"""Runs the demo's preset ChalkSQL queries and serves the page that shows them.

The replica authenticates to ChalkSQL with its own workload identity (the ScalingGroup is deployed
with `chalk_identity=True`), so it holds no client secret. The model gateway's API key arrives in
ROUTER_API_KEY from a Chalk secret, is bound into each query server-side, and never reaches the
browser: the SQL the page shows has `:gateway_url` and `:gateway_key` placeholders instead.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import deque
from pathlib import Path
from typing import Any

import uvicorn
from chalkcompute import SQLClient, SQLError
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from queries import MODELS, PRESETS, PRESETS_BY_ID, render

HERE = Path(__file__).resolve().parent
API_SERVER = os.environ["CHALK_API_SERVER"].rstrip("/")
GATEWAY_URL = f"{API_SERVER}/v1/router"
GATEWAY_KEY = os.environ["ROUTER_API_KEY"]

# Abuse limits for a public page. Preset results are cached, so only new (model, question)
# combinations reach the model; those are capped per visitor and in total.
MAX_QUESTION_CHARS = 160
CACHE_SECONDS = 15 * 60
VISITOR_RUNS_PER_HOUR = 20
GLOBAL_RUNS_PER_MINUTE = 30
MAX_CONCURRENT_QUERIES = 2
MAX_CACHED_RESULTS = 500

log = logging.getLogger("sql-llm-demo")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI()
sql = SQLClient()
_running = asyncio.Semaphore(MAX_CONCURRENT_QUERIES)
_cache: dict[tuple[str, str, str], tuple[float, dict[str, Any]]] = {}
_visitor_runs: dict[str, deque[float]] = {}
_global_runs: deque[float] = deque()


class RunRequest(BaseModel):
    preset: str
    model: str
    question: str | None = None


def _visitor(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (
        request.client.host if request.client else "unknown"
    )


def _admit(visitor: str) -> None:
    now = time.monotonic()
    while _global_runs and now - _global_runs[0] > 60:
        _global_runs.popleft()
    runs = _visitor_runs.setdefault(visitor, deque())
    while runs and now - runs[0] > 3600:
        runs.popleft()
    if len(_global_runs) >= GLOBAL_RUNS_PER_MINUTE:
        raise HTTPException(429, "The demo is busy. Try again in a minute.")
    if len(runs) >= VISITOR_RUNS_PER_HOUR:
        raise HTTPException(
            429,
            "You've run a lot of queries. Try again later, or pick a preset (presets are cached).",
        )
    runs.append(now)
    _global_runs.append(now)


def _clean_question(question: str | None) -> str | None:
    if question is None or not question.strip():
        return None
    q = " ".join(question.split())
    if len(q) > MAX_QUESTION_CHARS:
        raise HTTPException(
            400, f"Questions are limited to {MAX_QUESTION_CHARS} characters."
        )
    if any(not (ch.isprintable()) for ch in q):
        raise HTTPException(400, "Questions must be plain text.")
    return q


def _redact(message: str) -> str:
    return message.replace(GATEWAY_KEY, "<gateway key>")


def _run_sync(query: str) -> tuple[list[str], list[list[Any]], str]:
    result = sql.query(query, timeout=120.0)
    table = result.to_arrow()
    columns = table.column_names
    rows = [list(r.values()) for r in table.to_pylist()]
    return columns, rows, result.query_id


@app.get("/")
async def index() -> HTMLResponse:
    return HTMLResponse((HERE / "index.html").read_text())


@app.get("/api/config")
async def config() -> JSONResponse:
    return JSONResponse(
        {
            "models": MODELS,
            "max_question_chars": MAX_QUESTION_CHARS,
            "presets": [
                {
                    "id": p.id,
                    "title": p.title,
                    "function": p.function,
                    "blurb": p.blurb,
                    "custom_question": p.custom_question,
                    "default_question": p.default_question,
                    "model_columns": list(p.model_columns),
                }
                for p in PRESETS
            ],
        }
    )


@app.post("/api/sql")
async def show_sql(req: RunRequest) -> JSONResponse:
    preset = PRESETS_BY_ID.get(req.preset)
    if preset is None or req.model not in MODELS:
        raise HTTPException(400, "Unknown preset or model.")
    question = _clean_question(req.question)
    shown = render(
        preset, model=req.model, question=question, gateway_url=None, gateway_key=None
    )
    return JSONResponse({"sql": shown})


@app.post("/api/run")
async def run(req: RunRequest, request: Request) -> JSONResponse:
    preset = PRESETS_BY_ID.get(req.preset)
    if preset is None or req.model not in MODELS:
        raise HTTPException(400, "Unknown preset or model.")
    question = _clean_question(req.question) if preset.custom_question else None
    key = (preset.id, req.model, question or "")
    shown = render(
        preset, model=req.model, question=question, gateway_url=None, gateway_key=None
    )

    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < CACHE_SECONDS:
        return JSONResponse({**hit[1], "sql": shown, "cached": True})

    _admit(_visitor(request))
    query = render(
        preset,
        model=req.model,
        question=question,
        gateway_url=GATEWAY_URL,
        gateway_key=GATEWAY_KEY,
    )
    async with _running:
        t0 = time.perf_counter()
        try:
            columns, rows, query_id = await asyncio.to_thread(_run_sync, query)
        except SQLError as exc:
            log.warning("query failed: %s", _redact(str(exc))[:2000])
            raise HTTPException(
                502, "The query failed. Try again in a moment."
            ) from None
        elapsed_ms = round((time.perf_counter() - t0) * 1000)
    payload = {
        "columns": columns,
        "rows": rows,
        "elapsed_ms": elapsed_ms,
        "query_id": query_id,
        "model": req.model,
        "ran_at": time.time(),
    }
    if len(_cache) >= MAX_CACHED_RESULTS:
        del _cache[min(_cache, key=lambda k: _cache[k][0])]
    _cache[key] = (time.monotonic(), payload)
    log.info(
        "ran %s on %s in %d ms (%d rows, query %s)",
        preset.id,
        req.model,
        elapsed_ms,
        len(rows),
        query_id,
    )
    return JSONResponse({**payload, "sql": shown, "cached": False})


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
