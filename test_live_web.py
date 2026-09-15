import asyncio
from backend.fetchers.website import fetch_website_evidence

async def main():
    print("Testing live web fetcher with DuckDuckGo for 'moondream vlm'...")
    evidences = await fetch_website_evidence("moondream vlm")
    for ev in evidences:
        print(f"\n[ID]: {ev.evidence_id}")
        print(f"[URL]: {ev.source_url}")
        print(f"[Title]: {ev.title}")
        print(f"[Content Length]: {len(ev.normalized_content)} chars")
        print(f"[Snippet]: {ev.normalized_content[:200]}...")

if __name__ == "__main__":
    asyncio.run(main())
