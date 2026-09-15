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
from backend.llm import run_stage_a, run_stage_b, validate_evidence_ids


# Mode → which tools to run (Reddit paused until API key is configured)
MODE_TOOL_MAP = {
    ResearchMode.FULL: ["website", "youtube", "github"],
    ResearchMode.CONTENT: ["website", "youtube"],
    ResearchMode.DEVELOPER: ["github"],
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


async def _persist_findings_and_report(
    db_path: str,
    run_id: str,
    company_name: str,
    all_findings: list[dict],
    stage_b_result: dict,
    source_breakdown: list[dict],
):
    """Save findings and report to SQLite."""
    async with aiosqlite.connect(db_path) as db:
        # Insert findings
        for finding in all_findings:
            finding_id = str(uuid.uuid4())
            await db.execute(
                """
                INSERT OR REPLACE INTO findings (id, run_id, claim, claim_type, evidence_ids_json, confidence, source_category)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    finding_id,
                    run_id,
                    finding.get("claim", ""),
                    finding.get("claim_type", "observation"),
                    json.dumps(finding.get("evidence_ids", [])),
                    finding.get("confidence", 0.5),
                    finding.get("source_category", "general"),
                )
            )

        # Insert report
        report_id = str(uuid.uuid4())
        await db.execute(
            """
            INSERT OR REPLACE INTO reports (id, run_id, executive_summary, source_breakdown_json, cross_platform_findings, opportunity, limitations_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_id,
                run_id,
                stage_b_result.get("executive_summary", "Report generation incomplete."),
                json.dumps(source_breakdown),
                json.dumps(stage_b_result.get("cross_platform_findings", [])),
                stage_b_result.get("opportunity", "No opportunity identified."),
                json.dumps(stage_b_result.get("limitations", [])),
            )
        )
        await db.commit()


async def research_pipeline(ctx, run_id: str):
    """
    Full research pipeline executed by Arq worker.
    Steps: fetching_sources → normalizing → analyzing → synthesizing → completed
    """
    db_path = settings.DATABASE_PATH

    try:
        # 1. Load run info
        run_info = await _get_run_info(db_path, run_id)
        company_name = run_info["company_name"]
        website_url = run_info["website_url"]
        research_question = run_info["research_question"]
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

        # 4. Run all fetchers concurrently
        task_names = list(tasks.keys())
        start_time = time.perf_counter()
        raw_results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        parallel_time = time.perf_counter() - start_time

        # 5. Collect evidence, track failures
        all_evidence: list[Evidence] = []
        source_errors: dict[str, str] = {}
        source_breakdown = []

        for name, result in zip(task_names, raw_results):
            if isinstance(result, Exception):
                source_errors[name] = f"{type(result).__name__}: {str(result)}"
                source_breakdown.append({"source": name, "items_collected": 0, "status": "error", "error": str(result)})
                continue

            items = [result] if isinstance(result, Evidence) else result
            real_items = 0
            for item in items:
                all_evidence.append(item)
                if not (item.metadata.get("extraction_limited") and item.metadata.get("error")):
                    real_items += 1
                else:
                    source_errors[name] = item.metadata.get("error", "unknown error")

            status = "success" if real_items > 0 else "unavailable"
            source_breakdown.append({"source": name, "items_collected": real_items, "status": status, "error": source_errors.get(name)})

        print(f"[Worker] Parallel fetch: {parallel_time:.2f}s — {len(all_evidence)} items from {len(task_names)} sources")

        # 6. Status: normalizing
        await _update_status(db_path, run_id, "normalizing")
        normalized = normalize_evidence(all_evidence)
        final_evidence = [item.model_copy(update={"run_id": run_id}) for item in normalized]
        await _persist_evidence(db_path, final_evidence)
        print(f"[Worker] Normalized: {len(final_evidence)} items stored")

        # 7. Group evidence by source for Stage A
        evidence_by_source: dict[str, list[Evidence]] = {}
        for item in final_evidence:
            src = item.source.value
            evidence_by_source.setdefault(src, []).append(item)

        # 8. Status: analyzing (Stage A)
        await _update_status(db_path, run_id, "analyzing")
        stage_a_results = await run_stage_a(company_name, evidence_by_source)

        # Collect all per-source findings
        all_findings = []
        for sa in stage_a_results:
            all_findings.extend(sa.get("findings", []))

        # 9. Status: synthesizing (Stage B)
        await _update_status(db_path, run_id, "synthesizing")
        limitations = [f"{name}: {err}" for name, err in source_errors.items()]
        stage_b_result = await run_stage_b(company_name, stage_a_results, limitations, research_question)

        # Add cross-platform findings to all_findings
        all_findings.extend(stage_b_result.get("cross_platform_findings", []))

        # 10. Validate evidence IDs
        valid_ids = {item.evidence_id for item in final_evidence}
        all_findings = validate_evidence_ids(all_findings, valid_ids)

        # 11. Persist findings and report
        await _persist_findings_and_report(
            db_path, run_id, company_name,
            all_findings, stage_b_result, source_breakdown
        )

        # 12. Status: completed
        await _update_status(db_path, run_id, "completed")
        print(f"[Worker] Run {run_id} completed — {len(all_findings)} findings, report stored")

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
