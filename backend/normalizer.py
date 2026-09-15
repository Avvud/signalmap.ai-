"""
Evidence normalizer: deduplicates, trims, and reassigns sequential evidence IDs.
Runs after all fetchers complete, before evidence is sent to Groq.
"""

from typing import List
from backend.models import Evidence


def deduplicate_evidence(evidence_list: List[Evidence]) -> List[Evidence]:
    """
    Remove duplicate evidence items based on source_url.
    If two fetchers return the same URL, keep the one with longer content.
    """
    seen_urls: dict[str, Evidence] = {}
    for item in evidence_list:
        url = item.source_url.strip().rstrip("/")
        if url in seen_urls:
            # Keep the one with more content
            if len(item.normalized_content) > len(seen_urls[url].normalized_content):
                seen_urls[url] = item
        else:
            seen_urls[url] = item
    return list(seen_urls.values())


def trim_evidence(evidence_list: List[Evidence], max_chars: int = 1500) -> List[Evidence]:
    """
    Cap each evidence item's normalized_content to max_chars.
    This keeps Groq prompts small, fast, and cheap.
    """
    trimmed = []
    for item in evidence_list:
        content = item.normalized_content
        if len(content) > max_chars:
            content = content[:max_chars] + "\n\n[...content trimmed for brevity]"
        trimmed.append(item.model_copy(update={"normalized_content": content}))
    return trimmed


def reassign_evidence_ids(evidence_list: List[Evidence]) -> List[Evidence]:
    """
    Reassign sequential evidence IDs after dedup/trim.
    Format: {source_prefix}-{counter:03d} e.g. web-001, yt-002, rd-001, gh-003.
    """
    counters: dict[str, int] = {}
    reassigned = []
    for item in evidence_list:
        prefix = item.source.value[:3]  # "web", "you", "red", "git"
        # Use cleaner prefixes
        prefix_map = {"website": "web", "youtube": "yt", "reddit": "rd", "github": "gh"}
        prefix = prefix_map.get(item.source.value, prefix)
        counters[prefix] = counters.get(prefix, 0) + 1
        new_id = f"{prefix}-{counters[prefix]:03d}"
        reassigned.append(item.model_copy(update={"evidence_id": new_id}))
    return reassigned


def normalize_evidence(evidence_list: List[Evidence], max_chars: int = 1500) -> List[Evidence]:
    """
    Full normalization pipeline: deduplicate → trim → reassign IDs.
    Call this once after all fetchers complete.
    """
    deduped = deduplicate_evidence(evidence_list)
    trimmed = trim_evidence(deduped, max_chars)
    final = reassign_evidence_ids(trimmed)
    return final
