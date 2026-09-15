import time
import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.database import init_db
from backend.worker import research_pipeline


@pytest.mark.asyncio
async def test_post_research_fast_response():
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        start_time = time.perf_counter()
        response = await client.post("/api/research", json={
            "company_name": "TestCorp",
            "website_url": "https://testcorp.com",
            "research_question": "What is their core developer positioning?",
            "mode": "full"
        })
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        assert response.status_code == 200
        data = response.json()
        assert "run_id" in data
        assert data["company_name"] == "TestCorp"
        assert data["status"] == "queued"
        # Assert fast response under 100ms
        print(f"\n[Timing Check] POST /api/research completed in {elapsed_ms:.2f}ms")
        assert elapsed_ms < 100.0, f"Expected <100ms, got {elapsed_ms:.2f}ms"


@pytest.mark.asyncio
async def test_pipeline_status_progression():
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create job
        res = await client.post("/api/research", json={
            "company_name": "ProgressionTest",
            "mode": "full"
        })
        run_id = res.json()["run_id"]

        # Initial status
        status_res = await client.get(f"/api/research/{run_id}")
        assert status_res.status_code == 200
        assert status_res.json()["status"] == "queued"

        # Execute stub pipeline directly
        await research_pipeline(None, run_id)

        # Final status
        final_res = await client.get(f"/api/research/{run_id}")
        assert final_res.status_code == 200
        assert final_res.json()["status"] == "completed"

        # Check stub sources
        sources_res = await client.get(f"/api/research/{run_id}/sources")
        assert sources_res.status_code == 200
        sources_data = sources_res.json()
        assert sources_data["count"] == 1
        assert sources_data["evidence"][0]["evidence_id"] == "web-001"
