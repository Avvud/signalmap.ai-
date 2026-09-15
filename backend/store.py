"""
Durable state store for SignalMap AI.

Why this exists
---------------
On Vercel (and any Lambda-style serverless host) a local SQLite file is NOT a
usable database:

  * /tmp is per-instance. The instance that runs the pipeline is very often NOT
    the instance that serves the next GET /api/research/{run_id} poll, so the
    poller sees an empty database.
  * The execution environment is FROZEN as soon as the HTTP response is sent.
    Anything still running in a detached asyncio task resumes in a half-dead
    sandbox, where opening /tmp/signalmap.db raises
    `sqlite3.OperationalError: unable to open database file`.

So: if REDIS_URL points at a real (non-localhost) Redis, everything is stored
there as JSON blobs. Otherwise we fall back to SQLite, which is perfect for
local dev and for running the arq worker on a normal server.

Set REDIS_URL to an Upstash / Redis Cloud `rediss://...` URL in your Vercel
project env vars. Free tier is plenty for this.
"""

import json
import os
import time
import uuid
from typing import Any, Optional

import aiosqlite

from backend.config import settings

TTL_SECONDS = 60 * 60 * 24 * 7  # keep runs for 7 days

_redis = None
_redis_checked = False


def _redis_is_remote() -> bool:
    url = (settings.REDIS_URL or "").strip()
    if not url:
        return False
    return not ("localhost" in url or "127.0.0.1" in url)


async def get_redis():
    """Lazily create a redis.asyncio client. Returns None if unavailable."""
    global _redis, _redis_checked
    if _redis is not None:
        return _redis
    if _redis_checked or not _redis_is_remote():
        return None
    _redis_checked = True
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
        )
        await client.ping()
        _redis = client
        return _redis
    except Exception as exc:  # pragma: no cover - network dependent
        print(f"[store] Redis unavailable ({exc!r}); falling back to SQLite")
        return None


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


# --------------------------------------------------------------------------
# Public API — every endpoint and the worker go through these six functions.
# --------------------------------------------------------------------------


async def create_run(
    run_id: str,
    company_name: str,
    website_url: Optional[str],
    research_question: Optional[str],
    mode: str,
) -> dict:
    run = {
        "id": run_id,
        "company_name": company_name,
        "website_url": website_url,
        "research_question": research_question,
        "mode": mode,
        "status": "queued",
        "error_message": None,
        "created_at": _now(),
        "updated_at": _now(),
    }

    r = await get_redis()
    if r:
        await r.set(f"run:{run_id}", json.dumps(run), ex=TTL_SECONDS)
        return run

    await _sqlite_init()
    async with aiosqlite.connect(settings.get_database_path) as db:
        await db.execute(
            """
            INSERT INTO research_runs (id, company_name, website_url, research_question, mode, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (run_id, company_name, website_url, research_question, mode, "queued"),
        )
        await db.commit()
    return run


async def get_run(run_id: str) -> Optional[dict]:
    r = await get_redis()
    if r:
        raw = await r.get(f"run:{run_id}")
        return json.loads(raw) if raw else None

    try:
        async with aiosqlite.connect(settings.get_database_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM research_runs WHERE id = ?", (run_id,)
            ) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None
    except Exception as exc:
        print(f"[store] get_run failed: {exc!r}")
        return None


async def update_status(
    run_id: str, status: str, error_message: Optional[str] = None
) -> None:
    """Never raises. A status write failing must not kill the pipeline."""
    try:
        r = await get_redis()
        if r:
            raw = await r.get(f"run:{run_id}")
            run = json.loads(raw) if raw else {"id": run_id}
            run["status"] = status
            run["updated_at"] = _now()
            if error_message:
                run["error_message"] = error_message[:2000]
            await r.set(f"run:{run_id}", json.dumps(run), ex=TTL_SECONDS)
            return

        async with aiosqlite.connect(settings.get_database_path) as db:
            if error_message:
                await db.execute(
                    "UPDATE research_runs SET status = ?, error_message = ?, "
                    "updated_at = datetime('now') WHERE id = ?",
                    (status, error_message[:2000], run_id),
                )
            else:
                await db.execute(
                    "UPDATE research_runs SET status = ?, updated_at = datetime('now') "
                    "WHERE id = ?",
                    (status, run_id),
                )
            await db.commit()
    except Exception as exc:
        # This is the bug that produced the doubled traceback in the Vercel log:
        # the pipeline's `except` handler itself threw while writing "failed".
        print(f"[store] update_status({run_id}, {status}) failed: {exc!r}")


async def save_evidence(run_id: str, evidence_list: list) -> None:
    payload = [
        {
            "evidence_id": e.evidence_id,
            "run_id": run_id,
            "source": e.source.value,
            "source_url": e.source_url,
            "title": e.title,
            "raw_content": e.raw_content,
            "normalized_content": e.normalized_content,
            "metadata": e.metadata,
        }
        for e in evidence_list
    ]

    try:
        r = await get_redis()
        if r:
            await r.set(
                f"run:{run_id}:evidence", json.dumps(payload), ex=TTL_SECONDS
            )
            return

        async with aiosqlite.connect(settings.get_database_path) as db:
            for item in payload:
                await db.execute(
                    """
                    INSERT OR REPLACE INTO evidence
                      (id, run_id, source, source_url, title, raw_content,
                       normalized_content, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item["evidence_id"],
                        run_id,
                        item["source"],
                        item["source_url"],
                        item["title"],
                        item["raw_content"],
                        item["normalized_content"],
                        json.dumps(item["metadata"]),
                    ),
                )
            await db.commit()
    except Exception as exc:
        print(f"[store] save_evidence failed: {exc!r}")


async def get_evidence(run_id: str) -> list[dict]:
    r = await get_redis()
    if r:
        raw = await r.get(f"run:{run_id}:evidence")
        return json.loads(raw) if raw else []

    try:
        async with aiosqlite.connect(settings.get_database_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM evidence WHERE run_id = ?", (run_id,)
            ) as cur:
                rows = await cur.fetchall()
        return [
            {
                "evidence_id": r_["id"],
                "run_id": r_["run_id"],
                "source": r_["source"],
                "source_url": r_["source_url"],
                "title": r_["title"],
                "raw_content": r_["raw_content"],
                "normalized_content": r_["normalized_content"],
                "metadata": json.loads(r_["metadata_json"]) if r_["metadata_json"] else {},
            }
            for r_ in rows
        ]
    except Exception as exc:
        print(f"[store] get_evidence failed: {exc!r}")
        return []


async def save_report(
    run_id: str,
    company_name: str,
    all_findings: list[dict],
    stage_b_result: dict,
    source_breakdown: list[dict],
) -> None:
    report = {
        "id": str(uuid.uuid4()),
        "run_id": run_id,
        "company_name": company_name,
        "executive_summary": stage_b_result.get(
            "executive_summary", "Report generation incomplete."
        ),
        "findings": [
            {
                "id": str(uuid.uuid4()),
                "run_id": run_id,
                "claim": f.get("claim", ""),
                "claim_type": f.get("claim_type", "observation"),
                "evidence_ids": f.get("evidence_ids", []),
                "confidence": f.get("confidence", 0.5),
                "source_category": f.get("source_category", "general"),
            }
            for f in all_findings
        ],
        "cross_platform_findings": stage_b_result.get("cross_platform_findings", []),
        "opportunity": stage_b_result.get("opportunity", "No opportunity identified."),
        "source_breakdown": source_breakdown,
        "limitations": stage_b_result.get("limitations", []),
        "created_at": _now(),
    }

    try:
        r = await get_redis()
        if r:
            await r.set(f"run:{run_id}:report", json.dumps(report), ex=TTL_SECONDS)
            return

        async with aiosqlite.connect(settings.get_database_path) as db:
            for f in report["findings"]:
                await db.execute(
                    """
                    INSERT OR REPLACE INTO findings
                      (id, run_id, claim, claim_type, evidence_ids_json, confidence, source_category)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f["id"], run_id, f["claim"], f["claim_type"],
                        json.dumps(f["evidence_ids"]), f["confidence"], f["source_category"],
                    ),
                )
            await db.execute(
                """
                INSERT OR REPLACE INTO reports
                  (id, run_id, executive_summary, source_breakdown_json,
                   cross_platform_findings, opportunity, limitations_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report["id"], run_id, report["executive_summary"],
                    json.dumps(source_breakdown),
                    json.dumps(report["cross_platform_findings"]),
                    report["opportunity"],
                    json.dumps(report["limitations"]),
                ),
            )
            await db.commit()
    except Exception as exc:
        print(f"[store] save_report failed: {exc!r}")


async def get_report(run_id: str) -> Optional[dict]:
    r = await get_redis()
    if r:
        raw = await r.get(f"run:{run_id}:report")
        return json.loads(raw) if raw else None

    try:
        async with aiosqlite.connect(settings.get_database_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM reports WHERE run_id = ?", (run_id,)
            ) as cur:
                rep = await cur.fetchone()
            if not rep:
                return None
            async with db.execute(
                "SELECT * FROM findings WHERE run_id = ?", (run_id,)
            ) as cur:
                finding_rows = await cur.fetchall()
            run = await get_run(run_id) or {}

        return {
            "id": rep["id"],
            "run_id": run_id,
            "company_name": run.get("company_name", ""),
            "executive_summary": rep["executive_summary"],
            "findings": [
                {
                    "id": f["id"],
                    "run_id": f["run_id"],
                    "claim": f["claim"],
                    "claim_type": f["claim_type"],
                    "evidence_ids": json.loads(f["evidence_ids_json"]),
                    "confidence": f["confidence"],
                    "source_category": f["source_category"],
                }
                for f in finding_rows
            ],
            "cross_platform_findings": json.loads(rep["cross_platform_findings"])
            if rep["cross_platform_findings"] else [],
            "opportunity": rep["opportunity"],
            "source_breakdown": json.loads(rep["source_breakdown_json"]),
            "limitations": json.loads(rep["limitations_json"]),
            "created_at": rep["created_at"],
        }
    except Exception as exc:
        print(f"[store] get_report failed: {exc!r}")
        return None


# --------------------------------------------------------------------------
# SQLite bootstrap (local dev / self-hosted worker only)
# --------------------------------------------------------------------------

_sqlite_ready = False


async def _sqlite_init() -> None:
    global _sqlite_ready
    if _sqlite_ready:
        return
    path = settings.get_database_path
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as fh:
        schema_sql = fh.read()
    async with aiosqlite.connect(path) as db:
        await db.executescript(schema_sql)
        await db.commit()
    _sqlite_ready = True


async def init() -> None:
    """Called once at app startup. Safe to call repeatedly; never raises."""
    try:
        if await get_redis():
            print("[store] Using Redis-backed store")
            return
        await _sqlite_init()
        print(f"[store] Using SQLite store at {settings.get_database_path}")
    except Exception as exc:
        print(f"[store] init failed: {exc!r}")