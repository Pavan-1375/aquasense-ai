import asyncio
import logging
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request
from fastapi.responses import JSONResponse

from .api.routes import router
from .config import get_settings
from .db import SessionLocal, init_db
from .services.reminders import run_reminder_cycle
from .services.rate_limit import limiter


settings = get_settings()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s %(message)s")
logger = logging.getLogger("aquasense.api")
app = FastAPI(title="AquaSense AI API", version="0.1.0", description="Validated water-quality and groundwater monitoring API")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(router)
reminder_task: asyncio.Task | None = None


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    client_ip = request.client.host if request.client else "unknown"
    limited_paths = {"/api/auth/signin", "/api/auth/signup", "/api/auth/forgot-password", "/api/auth/reset-password", "/api/verification/request", "/api/verification/confirm"}
    is_ingest = request.url.path == "/api/ingest/http"
    if settings.rate_limit_enabled and request.method == "POST" and (request.url.path in limited_paths or is_ingest):
        limit = settings.rate_limit_ingest_requests if is_ingest else settings.rate_limit_auth_requests
        if not limiter.allow(f"{client_ip}:{request.url.path}", limit, settings.rate_limit_window_seconds):
            return JSONResponse(status_code=429, content={"detail": "Too many requests. Please retry later."}, headers={"Retry-After": str(settings.rate_limit_window_seconds)})
    started = perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled request failure", extra={"request_id": request_id})
        raise
    response.headers["X-Request-ID"] = request_id
    logger.info("%s %s -> %s in %.1fms", request.method, request.url.path, response.status_code, (perf_counter() - started) * 1000, extra={"request_id": request_id})
    return response


async def reminder_worker() -> None:
    app.state.reminder_worker_running = True
    while True:
        db = SessionLocal()
        try:
            run_reminder_cycle(db)
        except Exception:
            db.rollback()
        finally:
            db.close()
        await asyncio.sleep(max(30, settings.scheduler_interval_seconds))


@app.on_event("startup")
async def startup() -> None:
    global reminder_task
    init_db()
    app.state.reminder_worker_running = False
    if settings.scheduler_enabled:
        reminder_task = asyncio.create_task(reminder_worker())


@app.on_event("shutdown")
async def shutdown() -> None:
    app.state.reminder_worker_running = False
    if reminder_task:
        reminder_task.cancel()
        try:
            await reminder_task
        except asyncio.CancelledError:
            pass


@app.get("/")
def root() -> dict:
    return {"service": "AquaSense AI API", "docs": "/docs", "health": "/api/health"}

