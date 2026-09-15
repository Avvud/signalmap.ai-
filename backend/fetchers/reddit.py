from typing import List
import httpx
from backend.config import settings
from backend.models import RedditEvidence, SourceType

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SignalMapAI/1.0"


async def search_reddit(
    query: str, max_results: int = 5, run_id: str = "rd-run"
) -> List[RedditEvidence]:
    """
    Asynchronously searches Reddit for a query using asyncpraw if credentials exist,
    or falls back to Reddit's public REST JSON search.
    Extracts post title, selftext/content, subreddit, score, num_comments, and top comments.
    """
    results: List[RedditEvidence] = []
    client_id = settings.REDDIT_CLIENT_ID
    client_secret = settings.REDDIT_CLIENT_SECRET

    if client_id and client_secret and client_id != "your_client_id":
        try:
            import asyncpraw
            async with asyncpraw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=settings.REDDIT_USER_AGENT,
            ) as reddit:
                subreddit = await reddit.subreddit("all")
                idx = 1
                async for post in subreddit.search(query, limit=max_results):
                    title = post.title
                    score = post.score
                    num_comments = post.num_comments
                    sub_name = post.subreddit.display_name
                    post_url = f"https://reddit.com{post.permalink}"
                    selftext = post.selftext or ""

                    top_comments = []
                    post.comment_sort = "top"
                    await post.load()
                    for comment in post.comments[:2]:
                        if hasattr(comment, "body") and comment.body:
                            top_comments.append(comment.body[:300])

                    norm_text = (
                        f"Title: {title}\n"
                        f"Subreddit: r/{sub_name} | Score: {score} | Comments: {num_comments}\n"
                        f"URL: {post_url}\n\n"
                        f"Post Body:\n{selftext[:1000]}\n\n"
                        f"Top Comments:\n" + "\n-\n".join(top_comments)
                    )

                    results.append(
                        RedditEvidence(
                            evidence_id=f"rd-{idx:03d}",
                            run_id=run_id,
                            source=SourceType.REDDIT,
                            source_url=post_url,
                            title=title,
                            raw_content=norm_text,
                            normalized_content=norm_text,
                            metadata={
                                "subreddit": sub_name,
                                "score": score,
                                "num_comments": num_comments,
                                "top_comments": top_comments,
                                "extraction_limited": False,
                            },
                        )
                    )
                    idx += 1
                if results:
                    return results
        except Exception:
            pass

    # Public REST JSON Fallback (unauthenticated scraping)
    try:
        headers = {"User-Agent": USER_AGENT}
        async with httpx.AsyncClient(headers=headers, timeout=10.0, follow_redirects=True) as client:
            res = await client.get(
                "https://www.reddit.com/search.json",
                params={"q": query, "limit": max_results, "sort": "relevance"},
            )
            res.raise_for_status()
            data = res.json()
            posts = data.get("data", {}).get("children", [])

            for idx, child in enumerate(posts, 1):
                pdata = child.get("data", {})
                title = pdata.get("title", "")
                selftext = pdata.get("selftext", "")
                sub_name = pdata.get("subreddit", "")
                score = pdata.get("score", 0)
                num_comments = pdata.get("num_comments", 0)
                permalink = pdata.get("permalink", "")
                post_url = f"https://reddit.com{permalink}" if permalink else f"https://reddit.com/r/{sub_name}"

                norm_text = (
                    f"Title: {title}\n"
                    f"Subreddit: r/{sub_name} | Score: {score} | Comments: {num_comments}\n\n"
                    f"Post Content:\n{selftext[:1000]}"
                )

                results.append(
                    RedditEvidence(
                        evidence_id=f"rd-{idx:03d}",
                        run_id=run_id,
                        source=SourceType.REDDIT,
                        source_url=post_url,
                        title=title,
                        raw_content=norm_text,
                        normalized_content=norm_text,
                        metadata={
                            "subreddit": sub_name,
                            "score": score,
                            "num_comments": num_comments,
                            "top_comments": [],
                            "extraction_limited": False,
                        },
                    )
                )

    except Exception as e:
        results = [
            RedditEvidence(
                evidence_id="rd-err",
                run_id=run_id,
                source=SourceType.REDDIT,
                source_url=f"https://reddit.com/search?q={query}",
                title=f"Reddit Search: {query}",
                raw_content=f"Error fetching Reddit data: {str(e)}",
                normalized_content=f"Reddit source unavailable: {type(e).__name__} - {str(e)}",
                metadata={"extraction_limited": True, "error": str(e)},
            )
        ]

    return results
