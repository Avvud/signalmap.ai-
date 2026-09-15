import re
from typing import List, Optional
from urllib.parse import urlparse, urljoin
import httpx
from bs4 import BeautifulSoup
from backend.models import WebsiteEvidence, SourceType


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 SignalMapAI/1.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def _clean_text(text: str) -> str:
    """Normalize whitespace and strip extraneous empty lines."""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


async def inspect_website(
    url: str, run_id: str = "web-run", evidence_id: str = "web-001"
) -> WebsiteEvidence:
    """
    Asynchronously inspects a website URL using httpx and BeautifulSoup.
    Extracts title, meta description, headings, main text, and internal links.
    Handles timeouts, 404s, and JS-heavy empty pages gracefully without crashing.
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    domain = urlparse(url).netloc
    extraction_limited = False
    raw_html = ""
    title = domain
    meta_description = ""
    headings: List[str] = []
    internal_links: List[str] = []
    normalized_content = ""

    try:
        async with httpx.AsyncClient(
            headers=DEFAULT_HEADERS,
            timeout=10.0,
            follow_redirects=True,
            verify=False,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            raw_html = response.text

        soup = BeautifulSoup(raw_html, "html.parser")

        # 1. Extract Title
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            title = title_tag.string.strip()
        else:
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                title = str(og_title["content"]).strip()

        # 2. Extract Meta Description
        meta_desc_tag = soup.find("meta", attrs={"name": re.compile(r"description", re.I)})
        if meta_desc_tag and meta_desc_tag.get("content"):
            meta_description = str(meta_desc_tag["content"]).strip()
        else:
            og_desc = soup.find("meta", property="og:description")
            if og_desc and og_desc.get("content"):
                meta_description = str(og_desc["content"]).strip()

        # 3. Strip non-content structural elements (nav, footer, script, style, header, etc.)
        for element in soup(["script", "style", "nav", "footer", "header", "noscript", "form", "iframe", "svg"]):
            element.decompose()

        # 4. Extract Headings (h1, h2, h3)
        heading_tags = soup.find_all(["h1", "h2", "h3"])
        for h in heading_tags:
            h_text = h.get_text(strip=True)
            if h_text and len(h_text) > 2:
                headings.append(h_text)

        # 5. Extract Internal Links (limit to top 15 unique links)
        seen_links = set()
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            full_url = urljoin(url, href)
            parsed_full = urlparse(full_url)
            if parsed_full.netloc == domain and full_url not in seen_links:
                seen_links.add(full_url)
                internal_links.append(full_url)
                if len(internal_links) >= 15:
                    break

        # 6. Extract Main Body Text
        paragraphs = []
        main_content_area = soup.find("main") or soup.find("article") or soup.body or soup
        for p in main_content_area.find_all(["p", "li"]):
            p_text = p.get_text(strip=True)
            if len(p_text) > 15:
                paragraphs.append(p_text)

        raw_extracted_text = "\n\n".join(paragraphs) if paragraphs else main_content_area.get_text(separator="\n", strip=True)
        normalized_content = _clean_text(raw_extracted_text)

        # Check if content is empty or JS-heavy (near empty)
        if len(normalized_content) < 100:
            extraction_limited = True
            if meta_description:
                normalized_content = f"Page text limited (JS-rendered or minimal). Meta description: {meta_description}"
            else:
                normalized_content = "Page text extraction limited (JS-rendered client app or minimal HTML)."

    except httpx.HTTPStatusError as e:
        extraction_limited = True
        normalized_content = f"HTTP error {e.response.status_code} while fetching website."
    except httpx.TimeoutException:
        extraction_limited = True
        normalized_content = "Connection timed out while fetching website."
    except Exception as e:
        extraction_limited = True
        normalized_content = f"Failed to inspect website: {type(e).__name__} - {str(e)}"

    metadata = {
        "meta_description": meta_description,
        "headings": headings[:10],
        "internal_links": internal_links,
        "extraction_limited": extraction_limited,
        "content_length": len(normalized_content),
    }

    return WebsiteEvidence(
        evidence_id=evidence_id,
        run_id=run_id,
        source=SourceType.WEBSITE,
        source_url=url,
        title=title,
        raw_content=raw_html[:2000] if raw_html else normalized_content,
        normalized_content=normalized_content,
        metadata=metadata,
    )
