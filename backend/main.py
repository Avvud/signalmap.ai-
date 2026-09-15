import json
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Request
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


limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB
    await init_db()
    # Create Redis Pool for Arq
    try:
        app.state.redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    except Exception as e:
        print(f"Warning: Could not connect to Redis at {settings.REDIS_URL}: {e}")
        app.state.redis = None
    yield
    if app.state.redis:
        await app.state.redis.close()


app = FastAPI(title="SignalMap AI API", version="1.0.0", lifespan=lifespan)
app.state.redis = None

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/research", response_model=RunStatusResponse)
@limiter.limit("10/minute")
async def create_research(request: Request, body: ResearchInput, db: aiosqlite.Connection = Depends(get_db)):
    run_id = str(uuid.uuid4())
    
    await db.execute(
        """
        INSERT INTO research_runs (id, company_name, website_url, research_question, mode, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (run_id, body.company_name, body.website_url, body.research_question, body.mode.value, "queued")
    )
    await db.commit()

    redis_pool = getattr(request.app.state, "redis", None)
    if redis_pool:
        await redis_pool.enqueue_job("research_pipeline", run_id)
    else:
        print(f"Redis pool unavailable. Job {run_id} created in SQLite DB.")

    async with db.execute("SELECT * FROM research_runs WHERE id = ?", (run_id,)) as cursor:
        row = await cursor.fetchone()
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


@app.get("/api/research/{run_id}", response_model=RunStatusResponse)
async def get_research_status(run_id: str, db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT * FROM research_runs WHERE id = ?", (run_id,)) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Research run not found")
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


@app.get("/api/research/{run_id}/sources")
async def get_research_sources(run_id: str, db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT * FROM research_runs WHERE id = ?", (run_id,)) as cursor:
        run = await cursor.fetchone()
        if not run:
            raise HTTPException(status_code=404, detail="Research run not found")

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
        return {"run_id": run_id, "count": len(evidence_list), "evidence": evidence_list}


@app.get("/health")
async def health_check():
    return {"status": "ok", "app": "SignalMap AI"}
