import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from backend import store
from backend.config import settings
from backend.models import ResearchInput, RunStatusResponse
from backend.worker import research_pipeline

# How long a single /execute request is allowed to run. Keep this a little
# under your vercel.json maxDuration so we can write status="failed" before
# the platform kills us.
PIPELINE_TIMEOUT_SECONDS = 260


# --- Structured logging ---------------------------------------------------
class JSONLogFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "time": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_obj["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


logger = logging.getLogger("signalmap")
logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
_handler = logging.StreamHandler()
_handler.setFormatter(JSONLogFormatter())
logger.addHandler(_handler)

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing SignalMap AI FastAPI app")
    await store.init()

    app.state.arq = None
    # Arq/Redis job queue is only used when we are NOT on serverless — on
    # Vercel there is no long-lived worker process to consume the queue.
    if not settings.is_vercel:
        try:
            from arq import create_pool
            from arq.connections import RedisSettings

            app.state.arq = await create_pool(
                RedisSettings.from_dsn(settings.REDIS_URL)
            )
            logger.info("Connected to Arq/Redis queue")
        except Exception as exc:
            logger.warning(f"Arq queue unavailable ({exc}); running pipelines inline")

    yield

    logger.info("Shutting down SignalMap AI FastAPI app")
    if getattr(app.state, "arq", None):
        await app.state.arq.close()


app = FastAPI(title="SignalMap AI API", version="1.1.0", lifespan=lifespan)
app.state.arq = None
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        f"Unhandled exception on {request.method} {request.url.path}: {exc}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again later."},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    logger.info(
        f"{request.method} {request.url.path} - {response.status_code} "
        f"- {time.time() - start:.3f}s"
    )
    return response


def _to_response(run: dict) -> RunStatusResponse:
    return RunStatusResponse(
        run_id=run["id"],
        company_name=run["company_name"],
        website_url=run.get("website_url"),
        research_question=run.get("research_question"),
        mode=run["mode"],
        status=run["status"],
        error_message=run.get("error_message"),
        created_at=run["created_at"],
        updated_at=run["updated_at"],
    )


# --- Endpoints ------------------------------------------------------------


@app.post("/api/research", response_model=RunStatusResponse)
@limiter.limit("10/minute")
async def create_research(request: Request, body: ResearchInput):
    """
    Creates the run row and returns immediately.

    It deliberately does NOT start the pipeline with asyncio.create_task().
    On Vercel the execution environment is frozen the moment this response is
    sent, so a detached task resumes in a dead sandbox — which is exactly what
    produced `Task exception was never retrieved` +
    `OperationalError: unable to open database file`.
    """
    run_id = str(uuid.uuid4())
    logger.info(
        f"Creating research run {run_id} for {body.company_name} (mode: {body.mode.value})"
    )

    run = await store.create_run(
        run_id=run_id,
        company_name=body.company_name,
        website_url=body.website_url,
        research_question=body.research_question,
        mode=body.mode.value,
    )

    arq = getattr(request.app.state, "arq", None)
    if arq:
        await arq.enqueue_job("research_pipeline", run_id)
        logger.info(f"Enqueued run {run_id} on Arq")
    else:
        # The client is responsible for calling POST /api/research/{id}/execute.
        logger.info(f"Run {run_id} queued; awaiting /execute call from client")

    return _to_response(run)


@app.post("/api/research/{run_id}/execute", response_model=RunStatusResponse)
@limiter.limit("10/minute")
async def execute_research(request: Request, run_id: str):
    """
    Runs the pipeline inside this request and holds the connection open until
    it finishes. The browser fires this and does not await it; it polls
    GET /api/research/{run_id} for progress instead.
    """
    run = await store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Research run not found")

    if run["status"] not in ("queued", "failed"):
        return _to_response(run)

    try:
        await asyncio.wait_for(
            research_pipeline(None, run_id), timeout=PIPELINE_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        logger.error(f"Run {run_id} exceeded {PIPELINE_TIMEOUT_SECONDS}s")
        await store.update_status(
            run_id,
            "failed",
            error_message=(
                f"Pipeline exceeded the {PIPELINE_TIMEOUT_SECONDS}s serverless "
                "time budget. Try a narrower mode (developer/messaging)."
            ),
        )
    except Exception as exc:
        logger.error(f"Run {run_id} failed: {exc}", exc_info=True)
        await store.update_status(
            run_id, "failed", error_message=f"{type(exc).__name__}: {exc}"
        )

    return _to_response(await store.get_run(run_id) or run)


@app.get("/api/research/{run_id}", response_model=RunStatusResponse)
@limiter.limit("120/minute")
async def get_research_status(request: Request, run_id: str):
    run = await store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Research run not found")
    return _to_response(run)


@app.get("/api/research/{run_id}/report")
@limiter.limit("60/minute")
async def get_research_report(request: Request, run_id: str):
    run = await store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Research run not found")

    report = await store.get_report(run_id)
    if not report:
        raise HTTPException(
            status_code=404,
            detail=f"Report not ready (run status: {run['status']})",
        )
    report["company_name"] = report.get("company_name") or run["company_name"]
    return report


@app.get("/api/research/{run_id}/sources")
@limiter.limit("60/minute")
async def get_research_sources(request: Request, run_id: str):
    evidence = await store.get_evidence(run_id)
    return {"run_id": run_id, "count": len(evidence), "evidence": evidence}


@app.get("/health")
async def health_check():
    backend = "redis" if await store.get_redis() else "sqlite"
    return {"status": "ok", "app": "SignalMap AI", "store": backend}