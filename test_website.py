import asyncio
import json
from backend.fetchers.website import inspect_website


async def main():
    test_urls = [
        "https://fastapi.tiangolo.com",
        "https://python.org",
        "https://httpbin.org/status/404"
    ]

    print("=== Phase 2: Standalone Website Fetcher Test ===")
    for i, url in enumerate(test_urls, 1):
        print(f"\n--- Testing Site {i}: {url} ---")
        evidence = await inspect_website(url, run_id="test-run-phase2", evidence_id=f"web-00{i}")
        
        print(f"Evidence ID: {evidence.evidence_id}")
        print(f"Source URL:  {evidence.source_url}")
        print(f"Title:       {evidence.title}")
        print(f"Meta Desc:   {evidence.metadata.get('meta_description')[:100]}...")
        print(f"Headings:    {evidence.metadata.get('headings')[:3]}")
        print(f"Limited?:    {evidence.metadata.get('extraction_limited')}")
        print(f"Content Len: {len(evidence.normalized_content)} chars")
        print("Content Snippet:")
        print(f"'{evidence.normalized_content[:300]}...'")

if __name__ == "__main__":
    asyncio.run(main())
