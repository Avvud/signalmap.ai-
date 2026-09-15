import asyncio
import json
import time
import uuid
import aiosqlite
from arq.connections import RedisSettings
from backend.config import settings
from backend.models import Evidence, ResearchMode
from backend.normalizer import normalize_evidence
from backend.fetchers.website import inspect_website
from backend.fetchers.youtube import search_youtube
from backend.fetchers.reddit import search_reddit
from backend.fetchers.github import search_github


# Mode → which tools to run
MODE_TOOL_MAP = {
    ResearchMode.FULL: ["website", "youtube", "reddit", "github"],
    ResearchMode.CONTENT: ["website", "youtube"],
    ResearchMode.DEVELOPER: ["reddit", "github"],
    ResearchMode.MESSAGING: ["website"],
}


async def _update_status(db_path: str, run_id: str, status: str, error_message: str = None):
    """Helper to update run status in SQLite."""
    async with aiosqlite.connect(db_path) as db:
        if error_message:
            await db.execute(
                "UPDATE research_runs SET status = ?, error_message = ?, updated_at = datetime('now') WHERE id = ?",
                (status, error_message, run_id)
            )
        else:
            await db.execute(
                "UPDATE research_runs SET status = ?, updated_at = datetime('now') WHERE id = ?",
                (status, run_id)
            )
        await db.commit()


async def _get_run_info(db_path: str, run_id: str) -> dict:
    """Fetch run details from SQLite."""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM research_runs WHERE id = ?", (run_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                raise ValueError(f"Run {run_id} not found in database")
            return dict(row)


async def _persist_evidence(db_path: str, evidence_list: list[Evidence]):
    """Batch insert evidence items into SQLite."""
    async with aiosqlite.connect(db_path) as db:
        for item in evidence_list:
            await db.execute(
                """
                INSERT OR REPLACE INTO evidence (id, run_id, source, source_url, title, raw_content, normalized_content, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.evidence_id,
                    item.run_id,
                    item.source.value,
                    item.source_url,
                    item.title,
                    item.raw_content,
                    item.normalized_content,
                    json.dumps(item.metadata),
                )
            )
        await db.commit()


async def research_pipeline(ctx, run_id: str):
    """
    Full research pipeline executed by Arq worker.
    Steps: fetching_sources → normalizing → (Phase 5: analyzing → synthesizing) → completed
    """
    db_path = settings.DATABASE_PATH

    try:
        # 1. Load run info
        run_info = await _get_run_info(db_path, run_id)
        company_name = run_info["company_name"]
        website_url = run_info["website_url"]
        mode = ResearchMode(run_info["mode"])
        tools_to_run = MODE_TOOL_MAP[mode]

        # 2. Status: fetching_sources
        await _update_status(db_path, run_id, "fetching_sources")

        # 3. Build async tasks based on mode
        query = company_name
        tasks = {}
        if "website" in tools_to_run and website_url:
            tasks["website"] = inspect_website(website_url, run_id=run_id)
        elif "website" in tools_to_run:
            tasks["website"] = inspect_website(f"https://{company_name.lower().replace(' ', '')}.com", run_id=run_id)

        if "youtube" in tools_to_run:
            tasks["youtube"] = search_youtube(query, max_results=5, run_id=run_id)

        if "reddit" in tools_to_run:
            tasks["reddit"] = search_reddit(query, max_results=5, run_id=run_id)

        if "github" in tools_to_run:
            tasks["github"] = search_github(query, max_results=5, run_id=run_id)

        # 4. Run all fetchers concurrently via asyncio.gather
        task_names = list(tasks.keys())
        start_time = time.perf_counter()
        raw_results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        parallel_time = time.perf_counter() - start_time

        # 5. Collect evidence, handle partial failures
        all_evidence: list[Evidence] = []
        source_errors: dict[str, str] = {}

        for name, result in zip(task_names, raw_results):
            if isinstance(result, Exception):
                source_errors[name] = f"{type(result).__name__}: {str(result)}"
                print(f"[Worker] Source '{name}' failed: {source_errors[name]}")
                continue

            if isinstance(result, list):
                # Check if the list contains error evidence
                for item in result:
                    if item.metadata.get("extraction_limited") and item.metadata.get("error"):
                        source_errors[name] = item.metadata["error"]
                    all_evidence.append(item)
            elif isinstance(result, Evidence):
                if result.metadata.get("extraction_limited") and result.metadata.get("error"):
                    source_errors[name] = result.metadata["error"]
                all_evidence.append(result)

        print(f"[Worker] Parallel fetch completed in {parallel_time:.2f}s — {len(all_evidence)} raw items from {len(task_names)} sources")
        if source_errors:
            print(f"[Worker] Source errors: {source_errors}")

        # 6. Status: normalizing
        await _update_status(db_path, run_id, "normalizing")

        # 7. Normalize: deduplicate, trim, reassign IDs
        normalized = normalize_evidence(all_evidence)
        # Update run_id on all evidence items (they might have varied run_ids from default params)
        final_evidence = [item.model_copy(update={"run_id": run_id}) for item in normalized]

        print(f"[Worker] After normalization: {len(final_evidence)} items (deduped from {len(all_evidence)})")

        # 8. Persist evidence to SQLite
        await _persist_evidence(db_path, final_evidence)

        # 9. Status: analyzing (Phase 5 will add Groq here)
        # For now, mark as completed since we stop after evidence storage
        await _update_status(db_path, run_id, "completed")
        print(f"[Worker] Run {run_id} completed — {len(final_evidence)} evidence items stored")

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        print(f"[Worker] Pipeline failed for run {run_id}: {error_msg}")
        await _update_status(db_path, run_id, "failed", error_message=error_msg)


async def startup(ctx):
    pass


async def shutdown(ctx):
    pass


class WorkerSettings:
    functions = [research_pipeline]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
