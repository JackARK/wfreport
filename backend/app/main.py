from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import time

from backend.core.logging_conf import setup_logging, get_logger
from backend.app.api import router

setup_logging()
logger = get_logger("main")

load_dotenv()

app = FastAPI(title="王凡周报生成器")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log every HTTP request: method, path, duration, status code.
    Skips /docs and /openapi.json to avoid noise."""
    path = request.url.path
    if path in ("/docs", "/openapi.json", "/favicon.ico"):
        return await call_next(request)
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info("%s %s → %d (%.0fms)", request.method, path,
                response.status_code, elapsed_ms)
    return response


app.include_router(router)

logger.info("FastAPI app initialised")

_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="frontend")
    logger.info("serving frontend from %s", _dist)
else:
    logger.info("no frontend/dist found — API-only mode")
