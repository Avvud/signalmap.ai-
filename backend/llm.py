"""
Groq LLM client for SignalMap AI.
Uses the OpenAI-compatible client pointed at Groq's API.
Two-stage synthesis:
  Stage A: Per-source analysis (one call per source type)
  Stage B: Cross-platform synthesis (one call over Stage A outputs)
"""

import json
from typing import Any
from openai import AsyncOpenAI
from backend.config import settings
from backend.models import Evidence
from backend.prompts import build_stage_a_prompt, build_stage_b_prompt, build_evidence_block


def _get_client() -> AsyncOpenAI:
    """Create an async OpenAI client pointed at Groq's API."""
    return AsyncOpenAI(
        api_key=settings.GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1",
    )


async def _call_groq(system_prompt: str, user_prompt: str, attempt: int = 1) -> dict:
    """
    Make a single Groq API call with JSON mode.
    Retries once on parse failure with an error-correction prompt.
    On second failure, raises the error.
    """
    client = _get_client()

    response = await client.chat.completions.create(
        model=settings.GROQ_TEXT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
        max_tokens=4096,
    )

    raw_text = response.choices[0].message.content.strip()

    try:
        parsed = json.loads(raw_text)
        return parsed
    except json.JSONDecodeError as e:
        if attempt >= 2:
            raise ValueError(f"Groq returned invalid JSON after 2 attempts: {str(e)}\nRaw: {raw_text[:500]}")

        # Retry with error correction prompt
        correction_prompt = (
            f"Your previous response was not valid JSON. The error was: {str(e)}\n"
            f"Please fix and return ONLY valid JSON. Previous response:\n{raw_text[:1000]}"
        )
        print(f"[LLM] JSON parse failed on attempt {attempt}, retrying with correction...")
        return await _call_groq(system_prompt, correction_prompt, attempt=2)


async def run_stage_a(
    company_name: str, evidence_by_source: dict[str, list[Evidence]]
) -> list[dict]:
    """
    Stage A: One Groq call per source type.
    Each call only sees its own source's evidence — keeps prompts focused and small.
    Returns a list of per-source result dicts.
    """
    stage_a_results = []

    for source_type, evidence_list in evidence_by_source.items():
        if not evidence_list:
            continue

        # Skip error-only evidence (where all items are extraction_limited with errors)
        real_evidence = [e for e in evidence_list if not (e.metadata.get("extraction_limited") and e.metadata.get("error"))]
        if not real_evidence:
            stage_a_results.append({
                "source": source_type,
                "findings": [],
                "source_summary": f"{source_type} data was unavailable or returned errors.",
            })
            continue

        system_prompt, user_prompt = build_stage_a_prompt(source_type, company_name, real_evidence)
        print(f"[LLM] Stage A: Analyzing {source_type} ({len(real_evidence)} items)...")

        try:
            result = await _call_groq(system_prompt, user_prompt)
            # Ensure source field is set
            result["source"] = source_type
            stage_a_results.append(result)
            findings_count = len(result.get("findings", []))
            print(f"[LLM] Stage A: {source_type} → {findings_count} findings")
        except Exception as e:
            print(f"[LLM] Stage A failed for {source_type}: {e}")
            stage_a_results.append({
                "source": source_type,
                "findings": [],
                "source_summary": f"Analysis failed for {source_type}: {str(e)}",
            })

    return stage_a_results


async def run_stage_b(
    company_name: str,
    stage_a_results: list[dict],
    limitations: list[str],
    research_question: str = None,
) -> dict:
    """
    Stage B: One Groq call over Stage A outputs.
    Produces: executive_summary, 3 cross-platform findings, 1 opportunity, limitations.
    """
    system_prompt, user_prompt = build_stage_b_prompt(
        company_name, stage_a_results, limitations, research_question
    )
    print(f"[LLM] Stage B: Synthesizing cross-platform report...")

    result = await _call_groq(system_prompt, user_prompt)
    print(f"[LLM] Stage B: Report synthesized — {len(result.get('cross_platform_findings', []))} cross-platform findings")
    return result


def validate_evidence_ids(findings: list[dict], valid_ids: set[str]) -> list[dict]:
    """
    Validate that every evidence_id referenced in findings actually exists.
    Remove any invalid IDs and flag if a finding has zero valid references.
    """
    validated = []
    for f in findings:
        original_ids = f.get("evidence_ids", [])
        valid = [eid for eid in original_ids if eid in valid_ids]
        if not valid and original_ids:
            # All IDs were invalid — keep the finding but note it
            f["evidence_ids"] = original_ids  # Keep originals for debugging
            f["confidence"] = max(0.1, f.get("confidence", 0.5) - 0.3)  # Penalize confidence
        else:
            f["evidence_ids"] = valid if valid else original_ids
        validated.append(f)
    return validated
