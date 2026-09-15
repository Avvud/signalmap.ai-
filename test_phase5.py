"""
Phase 5 Test: Full end-to-end pipeline with Groq synthesis.
Runs a real research job for a real company, then:
  1. Shows the report JSON
  2. Verifies observation/interpretation/hypothesis are distinct
  3. Verifies every evidence_id resolves to a stored record
"""

import asyncio
import json
import uuid
import aiosqlite
from backend.database import init_db
from backend.config import settings
from backend.worker import research_pipeline


async def main():
    print("=== Phase 5: Groq Two-Stage Synthesis Test ===\n")
    await init_db()

    # Create a real research run
    run_id = str(uuid.uuid4())
    async with aiosqlite.connect(settings.DATABASE_PATH) as db:
        await db.execute(
            "INSERT INTO research_runs (id, company_name, website_url, research_question, mode, status) VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, "FastAPI", "https://fastapi.tiangolo.com", "How is FastAPI positioned and adopted?", "full", "queued")
        )
        await db.commit()

    print(f"[Test] Created run {run_id}")
    print("[Test] Running full pipeline with Groq synthesis...\n")

    await research_pipeline(None, run_id)

    # Read and display results
    async with aiosqlite.connect(settings.DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Run status
        async with db.execute("SELECT * FROM research_runs WHERE id = ?", (run_id,)) as cursor:
            run = await cursor.fetchone()
            print(f"\n{'='*60}")
            print(f"FINAL STATUS: {run['status']}")
            if run['error_message']:
                print(f"ERROR: {run['error_message']}")
                return

        # Evidence
        async with db.execute("SELECT id FROM evidence WHERE run_id = ?", (run_id,)) as cursor:
            evidence_rows = await cursor.fetchall()
            valid_ids = {r["id"] for r in evidence_rows}
            print(f"Evidence items stored: {len(valid_ids)}")
            print(f"Evidence IDs: {sorted(valid_ids)}")

        # Findings
        async with db.execute("SELECT * FROM findings WHERE run_id = ?", (run_id,)) as cursor:
            findings = await cursor.fetchall()
            print(f"\nFindings: {len(findings)}")
            
            claim_types_seen = set()
            invalid_refs = 0
            for f in findings:
                ct = f["claim_type"]
                claim_types_seen.add(ct)
                eids = json.loads(f["evidence_ids_json"])
                valid_count = sum(1 for eid in eids if eid in valid_ids)
                if valid_count < len(eids):
                    invalid_refs += 1
                print(f"  [{ct.upper():15}] (conf={f['confidence']:.2f}) {f['claim'][:80]}...")
                print(f"                    evidence_ids={eids}")

            print(f"\nClaim types seen: {claim_types_seen}")
            print(f"Findings with invalid evidence refs: {invalid_refs}")

        # Report
        async with db.execute("SELECT * FROM reports WHERE run_id = ?", (run_id,)) as cursor:
            report = await cursor.fetchone()
            if report:
                print(f"\n{'='*60}")
                print("EXECUTIVE SUMMARY:")
                print(report["executive_summary"])
                print(f"\nOPPORTUNITY:")
                print(report["opportunity"])
                print(f"\nLIMITATIONS:")
                print(json.dumps(json.loads(report["limitations_json"]), indent=2))
                print(f"\nSOURCE BREAKDOWN:")
                print(json.dumps(json.loads(report["source_breakdown_json"]), indent=2))
            else:
                print("\n[ERROR] No report found in database!")

    print(f"\n{'='*60}")
    print("=== PHASE 5 TEST COMPLETE ===")


if __name__ == "__main__":
    asyncio.run(main())
