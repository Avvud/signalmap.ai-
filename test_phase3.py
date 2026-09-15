import asyncio
from backend.fetchers.youtube import search_youtube
from backend.fetchers.reddit import search_reddit
from backend.fetchers.github import search_github


async def main():
    query = "FastAPI"
    print(f"=== Phase 3: External Fetchers Test (Query: '{query}') ===")

    # 1. Test YouTube
    print("\n--- Testing YouTube Fetcher ---")
    yt_items = await search_youtube(query, max_results=2, run_id="phase3-test")
    print(f"YouTube returned {len(yt_items)} items:")
    for item in yt_items:
        print(f"  [{item.evidence_id}] {item.title} ({item.source_url})")
        print(f"   Metadata: {item.metadata}")

    # 2. Test Reddit
    print("\n--- Testing Reddit Fetcher ---")
    rd_items = await search_reddit(query, max_results=2, run_id="phase3-test")
    print(f"Reddit returned {len(rd_items)} items:")
    for item in rd_items:
        print(f"  [{item.evidence_id}] {item.title} ({item.source_url})")
        print(f"   Subreddit: r/{item.metadata.get('subreddit')}, Score: {item.metadata.get('score')}")

    # 3. Test GitHub
    print("\n--- Testing GitHub Fetcher ---")
    gh_items = await search_github(query, max_results=2, run_id="phase3-test")
    print(f"GitHub returned {len(gh_items)} items:")
    for item in gh_items:
        print(f"  [{item.evidence_id}] {item.title} ({item.source_url})")
        print(f"   Stars: {item.metadata.get('stargazers_count')}, Lang: {item.metadata.get('language')}")

    print("\n=== ALL PHASE 3 FETCHERS TESTED ===")

if __name__ == "__main__":
    asyncio.run(main())
