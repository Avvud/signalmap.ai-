from typing import List
import httpx
from backend.config import settings
from backend.models import YouTubeEvidence, SourceType


async def search_youtube(
    query: str, max_results: int = 5, run_id: str = "yt-run"
) -> List[YouTubeEvidence]:
    """
    Asynchronously searches YouTube Data API v3 for a given query.
    Extracts title, video description, channel title, view count, like count, comment count, and publish date.
    Gracefully handles missing API keys or API quota/network failures.
    """
    api_key = settings.YOUTUBE_API_KEY
    if not api_key or api_key == "your_youtube_api_key":
        return [
            YouTubeEvidence(
                evidence_id="yt-001",
                run_id=run_id,
                source=SourceType.YOUTUBE,
                source_url="https://youtube.com",
                title=f"YouTube Search: {query}",
                raw_content="YouTube API key not configured.",
                normalized_content="YouTube source unavailable: API key not provided in .env.",
                metadata={"extraction_limited": True, "error": "API key missing"},
            )
        ]

    results: List[YouTubeEvidence] = []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            search_res = await client.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={
                    "key": api_key,
                    "q": query,
                    "type": "video",
                    "part": "snippet",
                    "maxResults": max_results,
                },
            )
            search_res.raise_for_status()
            search_data = search_res.json()
            items = search_data.get("items", [])

            if not items:
                return [
                    YouTubeEvidence(
                        evidence_id="yt-000",
                        run_id=run_id,
                        source=SourceType.YOUTUBE,
                        source_url=f"https://youtube.com/results?search_query={query}",
                        title=f"YouTube Search: {query}",
                        raw_content="No video results found.",
                        normalized_content=f"No YouTube videos found matching query '{query}'.",
                        metadata={"extraction_limited": False, "count": 0},
                    )
                ]

            video_ids = [item["id"]["videoId"] for item in items if "videoId" in item.get("id", {})]

            stats_map = {}
            if video_ids:
                stats_res = await client.get(
                    "https://www.googleapis.com/youtube/v3/videos",
                    params={
                        "key": api_key,
                        "id": ",".join(video_ids),
                        "part": "statistics",
                    },
                )
                if stats_res.status_code == 200:
                    for v_item in stats_res.json().get("items", []):
                        stats_map[v_item["id"]] = v_item.get("statistics", {})

            for idx, item in enumerate(items, 1):
                v_id = item["id"].get("videoId")
                if not v_id:
                    continue
                snippet = item.get("snippet", {})
                v_title = snippet.get("title", "")
                v_desc = snippet.get("description", "")
                channel = snippet.get("channelTitle", "")
                published_at = snippet.get("publishedAt", "")
                video_url = f"https://www.youtube.com/watch?v={v_id}"

                v_stats = stats_map.get(v_id, {})
                view_count = int(v_stats.get("viewCount", 0))
                like_count = int(v_stats.get("likeCount", 0))
                comment_count = int(v_stats.get("commentCount", 0))

                norm_text = (
                    f"Title: {v_title}\n"
                    f"Channel: {channel}\n"
                    f"Published: {published_at}\n"
                    f"Metrics: {view_count:,} views, {like_count:,} likes, {comment_count:,} comments\n\n"
                    f"Description:\n{v_desc}"
                )

                results.append(
                    YouTubeEvidence(
                        evidence_id=f"yt-{idx:03d}",
                        run_id=run_id,
                        source=SourceType.YOUTUBE,
                        source_url=video_url,
                        title=v_title,
                        raw_content=norm_text,
                        normalized_content=norm_text,
                        metadata={
                            "channel_title": channel,
                            "view_count": view_count,
                            "like_count": like_count,
                            "comment_count": comment_count,
                            "published_at": published_at,
                            "extraction_limited": False,
                        },
                    )
                )

    except Exception as e:
        results = [
            YouTubeEvidence(
                evidence_id="yt-err",
                run_id=run_id,
                source=SourceType.YOUTUBE,
                source_url=f"https://youtube.com/results?search_query={query}",
                title=f"YouTube Search: {query}",
                raw_content=f"Error fetching YouTube data: {str(e)}",
                normalized_content=f"YouTube API call failed: {type(e).__name__} - {str(e)}",
                metadata={"extraction_limited": True, "error": str(e)},
            )
        ]

    return results
