import asyncio
import time
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.database import init_db
from backend.worker import research_pipeline


async def main():
    print("=== SignalMap AI Phase 1 Test ===")
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Test POST /api/research response time (<100ms)
        start_time = time.perf_counter()
        response = await client.post("/api/research", json={
            "company_name": "FastAPI Company",
            "website_url": "https://fastapi.tiangolo.com",
            "research_question": "Investigate positioning",
            "mode": "full"
        })
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        print(f"POST /api/research status: {response.status_code}")
        print(f"Response time: {elapsed_ms:.2f}ms")
        assert response.status_code == 200
        data = response.json()
        run_id = data["run_id"]
        print(f"Created run_id: {run_id}, status: {data['status']}")
        assert elapsed_ms < 100.0, f"Expected <100ms, got {elapsed_ms:.2f}ms"

        # 2. Test GET /api/research/{run_id} status polling
        status_res = await client.get(f"/api/research/{run_id}")
        assert status_res.status_code == 200
        print(f"Initial polling status: {status_res.json()['status']}")

        # 3. Simulate Worker Pipeline execution
        print("\nRunning stub worker pipeline...")
        await research_pipeline(None, run_id)

        # 4. Check completed status
        final_res = await client.get(f"/api/research/{run_id}")
        assert final_res.status_code == 200
        final_status = final_res.json()["status"]
        print(f"Final polling status: {final_status}")
        assert final_status == "completed"

        # 5. Check sources endpoint
        sources_res = await client.get(f"/api/research/{run_id}/sources")
        assert sources_res.status_code == 200
        sources_data = sources_res.json()
        print(f"Sources endpoint count: {sources_data['count']}")
        assert sources_data["count"] == 1
        print("=== ALL PHASE 1 CHECKS PASSED ===")

if __name__ == "__main__":
    asyncio.run(main())
