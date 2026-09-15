import asyncio
import json
import logging
import uuid
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from arq import create_pool
from arq.connections import RedisSettings
import aiosqlite

from backend.config import settings
from backend.database import init_db, get_db
from backend.models import ResearchInput, RunStatusResponse, PipelineStatus
from backend.worker import research_pipeline

# In-memory caches for Vercel Serverless Functions
RUNS_CACHE = {}
REPORTS_CACHE = {}
SOURCES_CACHE = {}

# --- Structured Logging Setup ---
class JSONLogFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "time": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage()
        }
        if record.exc_info:
            log_obj["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)

logger = logging.getLogger("signalmap")
logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
handler = logging.StreamHandler()
handler.setFormatter(JSONLogFormatter())
logger.addHandler(handler)


limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing SignalMap AI FastAPI app")
    try:
        await init_db()
    except Exception as e:
        logger.error(f"Failed to initialize SQLite DB: {e}")

    # On Vercel, skip Redis connection to prevent 11s connection timeout
    if settings.is_vercel:
        logger.info("Vercel serverless mode: Skipping Redis pool initialization.")
        app.state.redis = None
    else:
        try:
            app.state.redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
            logger.info(f"Connected to Redis at {settings.REDIS_URL}")
        except Exception as e:
            logger.warning(f"Redis unavailable ({e}). Fallback to direct async execution mode.")
            app.state.redis = None
    yield
    logger.info("Shutting down SignalMap AI FastAPI app")
    if getattr(app.state, "redis", None):
        await app.state.redis.close()


app = FastAPI(title="SignalMap AI API", version="1.0.0", lifespan=lifespan)
app.state.redis = None

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- Global Exception Handler ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again later."},
    )

# --- Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(f"{request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s")
    return response


# --- Endpoints ---

@app.post("/api/research", response_model=RunStatusResponse)
@limiter.limit("10/minute")
async def create_research(request: Request, body: ResearchInput, db: aiosqlite.Connection = Depends(get_db)):
    run_id = str(uuid.uuid4())
    logger.info(f"Creating research run {run_id} for {body.company_name} (mode: {body.mode.value})")
    
    await db.execute(
        """
        INSERT INTO research_runs (id, company_name, website_url, research_question, mode, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (run_id, body.company_name, body.website_url, body.research_question, body.mode.value, "queued")
    )
    await db.commit()

    redis_pool = getattr(request.app.state, "redis", None)
    if settings.is_vercel or not redis_pool:
        logger.info(f"Synchronous pipeline execution mode for run {run_id}")
        await research_pipeline(None, run_id)
    else:
        await redis_pool.enqueue_job("research_pipeline", run_id)
        logger.info(f"Enqueued job for run {run_id} in Arq/Redis")

    async with db.execute("SELECT * FROM research_runs WHERE id = ?", (run_id,)) as cursor:
        row = await cursor.fetchone()
        if row:
            res = RunStatusResponse(
                run_id=row["id"],
                company_name=row["company_name"],
                website_url=row["website_url"],
                research_question=row["research_question"],
                mode=row["mode"],
                status=row["status"],
                error_message=row["error_message"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            RUNS_CACHE[run_id] = res
            return res

    fallback_res = RunStatusResponse(
        run_id=run_id,
        company_name=body.company_name,
        website_url=body.website_url,
        research_question=body.research_question,
        mode=body.mode,
        status=PipelineStatus.COMPLETED,
        created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        updated_at=time.strftime("%Y-%m-%d %H:%M:%S")
    )
    RUNS_CACHE[run_id] = fallback_res
    return fallback_res


@app.get("/api/research/{run_id}", response_model=RunStatusResponse)
@limiter.limit("60/minute")
async def get_research_status(request: Request, run_id: str, db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT * FROM research_runs WHERE id = ?", (run_id,)) as cursor:
        row = await cursor.fetchone()
        if row:
            return RunStatusResponse(
                run_id=row["id"],
                company_name=row["company_name"],
                website_url=row["website_url"],
                research_question=row["research_question"],
                mode=row["mode"],
                status=row["status"],
                error_message=row["error_message"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    if run_id in RUNS_CACHE:
        return RUNS_CACHE[run_id]

    logger.warning(f"Requested status for unknown run_id {run_id}")
    raise HTTPException(status_code=404, detail="Research run not found")


@app.get("/api/research/{run_id}/report")
@limiter.limit("30/minute")
async def get_research_report(request: Request, run_id: str, db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT * FROM research_runs WHERE id = ?", (run_id,)) as cursor:
        run = await cursor.fetchone()
        if not run and run_id in RUNS_CACHE:
            run = {"status": RUNS_CACHE[run_id].status, "company_name": RUNS_CACHE[run_id].company_name}
        elif not run:
            raise HTTPException(status_code=404, detail="Research run not found")

    async with db.execute("SELECT * FROM reports WHERE run_id = ?", (run_id,)) as cursor:
        report_row = await cursor.fetchone()

    if not report_row and run_id in REPORTS_CACHE:
        return REPORTS_CACHE[run_id]

    if not report_row:
        raise HTTPException(status_code=404, detail="Report data not found for completed run")

    async with db.execute("SELECT * FROM findings WHERE run_id = ?", (run_id,)) as cursor:
        finding_rows = await cursor.fetchall()
        findings = []
        for f in finding_rows:
            findings.append({
                "id": f["id"],
                "run_id": f["run_id"],
                "claim": f["claim"],
                "claim_type": f["claim_type"],
                "evidence_ids": json.loads(f["evidence_ids_json"]),
                "confidence": f["confidence"],
                "source_category": f["source_category"],
            })

    res = {
        "id": report_row["id"],
        "run_id": run_id,
        "company_name": run["company_name"],
        "executive_summary": report_row["executive_summary"],
        "findings": findings,
        "cross_platform_findings": json.loads(report_row["cross_platform_findings"]) if report_row["cross_platform_findings"] else [],
        "opportunity": report_row["opportunity"],
        "source_breakdown": json.loads(report_row["source_breakdown_json"]),
        "limitations": json.loads(report_row["limitations_json"]),
        "created_at": report_row["created_at"]
    }
    REPORTS_CACHE[run_id] = res
    return res


@app.get("/api/research/{run_id}/sources")
@limiter.limit("30/minute")
async def get_research_sources(request: Request, run_id: str, db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT * FROM evidence WHERE run_id = ?", (run_id,)) as cursor:
        rows = await cursor.fetchall()
        evidence_list = []
        for r in rows:
            evidence_list.append({
                "evidence_id": r["id"],
                "run_id": r["run_id"],
                "source": r["source"],
                "source_url": r["source_url"],
                "title": r["title"],
                "raw_content": r["raw_content"],
                "normalized_content": r["normalized_content"],
                "metadata": json.loads(r["metadata_json"]) if r["metadata_json"] else {}
            })

    if evidence_list:
        SOURCES_CACHE[run_id] = evidence_list
        return {"run_id": run_id, "count": len(evidence_list), "evidence": evidence_list}

    if run_id in SOURCES_CACHE:
        return {"run_id": run_id, "count": len(SOURCES_CACHE[run_id]), "evidence": SOURCES_CACHE[run_id]}

    return {"run_id": run_id, "count": 0, "evidence": []}


@app.get("/health")
async def health_check():
    return {"status": "ok", "app": "SignalMap AI"}
