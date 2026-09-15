"""
Phase 4 Test: Parallel orchestration + evidence pipeline.
Runs the full pipeline directly (no Redis needed) and verifies:
  1. Parallel execution timing
  2. Evidence normalization (dedup, trim, sequential IDs)
  3. SQLite persistence
  4. Partial failure handling
"""

import asyncio
import json
import time
import uuid
import os
import aiosqlite
from backend.database import init_db
from backend.config import settings
from backend.worker import research_pipeline


async def main():
    print("=== Phase 4: Parallel Orchestration + Evidence Pipeline Test ===\n")

    # Clean up any previous test DB
    await init_db()

    # Create a research run directly in SQLite
    run_id = str(uuid.uuid4())
    async with aiosqlite.connect(settings.DATABASE_PATH) as db:
        await db.execute(
            "INSERT INTO research_runs (id, company_name, website_url, mode, status) VALUES (?, ?, ?, ?, ?)",
            (run_id, "FastAPI", "https://fastapi.tiangolo.com", "full", "queued")
        )
        await db.commit()

    # Run the full pipeline
    print(f"[Test] Created run {run_id}, mode=full")
    print("[Test] Starting pipeline (all 4 sources concurrently)...\n")
    
    start = time.perf_counter()
    await research_pipeline(None, run_id)
    total_time = time.perf_counter() - start

    # Read results from SQLite
    async with aiosqlite.connect(settings.DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Check run status
        async with db.execute("SELECT * FROM research_runs WHERE id = ?", (run_id,)) as cursor:
            run = await cursor.fetchone()
            print(f"\n[Result] Final status: {run['status']}")
            if run['error_message']:
                print(f"[Result] Error: {run['error_message']}")

        # Check evidence
        async with db.execute("SELECT * FROM evidence WHERE run_id = ?", (run_id,)) as cursor:
            rows = await cursor.fetchall()
            print(f"[Result] Evidence items stored: {len(rows)}")
            
            sources_seen = {}
            for r in rows:
                src = r["source"]
                sources_seen[src] = sources_seen.get(src, 0) + 1
                print(f"  [{r['id']}] {src}: {r['title'][:60]}... ({len(r['normalized_content'])} chars)")

            print(f"\n[Result] Sources breakdown: {json.dumps(sources_seen, indent=2)}")

    print(f"\n[Timing] Total pipeline wall-clock time: {total_time:.2f}s")
    print("[Timing] Sequential would be ~4x longer (sum of individual fetch times)")
    
    # Test partial failure: run with developer mode (only reddit + github)
    print("\n\n--- Testing Partial Failure (developer mode, Reddit expected to fail) ---")
    run_id2 = str(uuid.uuid4())
    async with aiosqlite.connect(settings.DATABASE_PATH) as db:
        await db.execute(
            "INSERT INTO research_runs (id, company_name, website_url, mode, status) VALUES (?, ?, ?, ?, ?)",
            (run_id2, "React", None, "developer", "queued")
        )
        await db.commit()

    await research_pipeline(None, run_id2)

    async with aiosqlite.connect(settings.DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM research_runs WHERE id = ?", (run_id2,)) as cursor:
            run2 = await cursor.fetchone()
            print(f"[Result] Developer mode status: {run2['status']} (should be 'completed' even if Reddit fails)")

        async with db.execute("SELECT * FROM evidence WHERE run_id = ?", (run_id2,)) as cursor:
            rows2 = await cursor.fetchall()
            print(f"[Result] Evidence items: {len(rows2)}")
            for r in rows2:
                print(f"  [{r['id']}] {r['source']}: {r['title'][:60]}...")

    print("\n=== PHASE 4 TEST COMPLETE ===")


if __name__ == "__main__":
    asyncio.run(main())
