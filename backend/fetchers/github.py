from typing import List
import httpx
from backend.config import settings
from backend.models import GitHubEvidence, SourceType


async def search_github(
    query: str, max_results: int = 5, run_id: str = "gh-run"
) -> List[GitHubEvidence]:
    """
    Asynchronously searches GitHub REST API for repositories matching query.
    Extracts repo full_name, description, stargazers_count, forks_count, language, open_issues_count, and README content.
    Gracefully handles rate limits and API token errors.
    """
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "SignalMapAI/1.0",
    }
    if settings.GITHUB_TOKEN and settings.GITHUB_TOKEN != "ghp_your_token_here":
        headers["Authorization"] = f"token {settings.GITHUB_TOKEN}"

    results: List[GitHubEvidence] = []
    try:
        async with httpx.AsyncClient(headers=headers, timeout=10.0, follow_redirects=True) as client:
            search_res = await client.get(
                "https://api.github.com/search/repositories",
                params={"q": query, "per_page": max_results, "sort": "stars"},
            )
            search_res.raise_for_status()
            items = search_res.json().get("items", [])

            if not items:
                return [
                    GitHubEvidence(
                        evidence_id="gh-000",
                        run_id=run_id,
                        source=SourceType.GITHUB,
                        source_url=f"https://github.com/search?q={query}",
                        title=f"GitHub Search: {query}",
                        raw_content="No repository results found.",
                        normalized_content=f"No GitHub repositories found matching query '{query}'.",
                        metadata={"extraction_limited": False, "count": 0},
                    )
                ]

            for idx, repo in enumerate(items, 1):
                full_name = repo.get("full_name", "")
                html_url = repo.get("html_url", "")
                description = repo.get("description") or ""
                stars = repo.get("stargazers_count", 0)
                forks = repo.get("forks_count", 0)
                issues = repo.get("open_issues_count", 0)
                language = repo.get("language") or "Unknown"
                updated_at = repo.get("updated_at", "")

                readme_snippet = ""
                if idx == 1 and full_name:
                    try:
                        readme_res = await client.get(
                            f"https://raw.githubusercontent.com/{full_name}/main/README.md"
                        )
                        if readme_res.status_code == 200:
                            readme_snippet = readme_res.text[:1500]
                    except Exception:
                        pass

                norm_text = (
                    f"Repo: {full_name}\n"
                    f"Description: {description}\n"
                    f"Language: {language} | Stars: {stars:,} | Forks: {forks:,} | Open Issues: {issues:,}\n"
                    f"Last Updated: {updated_at}\n"
                    f"URL: {html_url}\n"
                )
                if readme_snippet:
                    norm_text += f"\nREADME Snippet:\n{readme_snippet}"

                results.append(
                    GitHubEvidence(
                        evidence_id=f"gh-{idx:03d}",
                        run_id=run_id,
                        source=SourceType.GITHUB,
                        source_url=html_url,
                        title=f"GitHub Repo: {full_name}",
                        raw_content=norm_text,
                        normalized_content=norm_text,
                        metadata={
                            "repo_name": full_name,
                            "stargazers_count": stars,
                            "forks_count": forks,
                            "language": language,
                            "open_issues_count": issues,
                            "extraction_limited": False,
                        },
                    )
                )

    except Exception as e:
        results = [
            GitHubEvidence(
                evidence_id="gh-err",
                run_id=run_id,
                source=SourceType.GITHUB,
                source_url=f"https://github.com/search?q={query}",
                title=f"GitHub Search: {query}",
                raw_content=f"Error fetching GitHub data: {str(e)}",
                normalized_content=f"GitHub source unavailable: {type(e).__name__} - {str(e)}",
                metadata={"extraction_limited": True, "error": str(e)},
            )
        ]

    return results
