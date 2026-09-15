"""
Engineered prompts for Groq synthesis.
Two-stage approach:
  Stage A: One call per source type → per-source structured findings
  Stage B: One call over Stage A outputs → cross-platform report

Every prompt enforces:
  - Observation / Interpretation / Hypothesis taxonomy
  - evidence_id citation on every claim
  - Never fabricate data — state "unavailable" if missing
"""

STAGE_A_SYSTEM = """You are a research analyst for SignalMap AI. You analyze text evidence collected from a single source about a company/product.

STRICT RULES:
1. Every claim MUST reference one or more evidence_ids from the provided evidence list.
2. Classify each finding as exactly one of:
   - "observation": Directly supported by the evidence text. High confidence.
   - "interpretation": A reasonable explanation of what the evidence suggests. Medium confidence.
   - "hypothesis": A theory that needs further validation. Lower confidence.
3. NEVER invent or fabricate information. If evidence is thin, say so explicitly.
4. NEVER blur the line between observation, interpretation, and hypothesis.
5. Keep findings concise and specific — no generic filler text.

Respond with valid JSON only. No markdown, no commentary outside the JSON."""

STAGE_A_USER = """Analyze the following {source_type} evidence for "{company_name}".

Evidence items:
{evidence_block}

Respond with this exact JSON structure:
{{
  "source": "{source_type}",
  "findings": [
    {{
      "claim": "specific factual claim here",
      "claim_type": "observation|interpretation|hypothesis",
      "evidence_ids": ["id-001", "id-002"],
      "confidence": 0.0 to 1.0,
      "source_category": "official_positioning|community_sentiment|developer_adoption|content_reach|ecosystem_presence"
    }}
  ],
  "source_summary": "2-3 sentence summary of what this source reveals about the company"
}}

Return 3-5 findings. Every finding must cite at least one evidence_id from the list above."""

STAGE_B_SYSTEM = """You are a senior research analyst for SignalMap AI. You synthesize per-source findings into a final cross-platform research report.

STRICT RULES:
1. Every claim MUST trace back to evidence_ids from the per-source findings.
2. Maintain the observation/interpretation/hypothesis taxonomy — never blur these.
3. Identify: what the company claims (official positioning), what creators/communities/developers actually say, where those diverge, and one non-obvious opportunity.
4. NEVER fabricate findings. If a source was unavailable, state it in limitations.
5. The executive summary should be 3-5 sentences, actionable, and grounded.

Respond with valid JSON only."""

STAGE_B_USER = """Synthesize these per-source findings into a final research report for "{company_name}".

{research_question_block}

Per-source analysis:
{stage_a_block}

Sources that were unavailable or had errors:
{limitations_block}

Respond with this exact JSON structure:
{{
  "executive_summary": "3-5 sentence summary of key insights",
  "cross_platform_findings": [
    {{
      "claim": "cross-source insight",
      "claim_type": "observation|interpretation|hypothesis",
      "evidence_ids": ["web-001", "yt-002"],
      "confidence": 0.0 to 1.0,
      "source_category": "cross_platform"
    }}
  ],
  "opportunity": "One non-obvious, evidence-backed opportunity or gap",
  "limitations": ["list of limitations or unavailable sources"]
}}

Return exactly 3 cross-platform findings and 1 opportunity. Each must cite evidence_ids."""


def build_evidence_block(evidence_list) -> str:
    """Format evidence items into a numbered text block for the prompt."""
    lines = []
    for item in evidence_list:
        lines.append(
            f"[{item.evidence_id}] ({item.source.value}) {item.title}\n"
            f"URL: {item.source_url}\n"
            f"Content: {item.normalized_content}\n"
        )
    return "\n---\n".join(lines)


def build_stage_a_prompt(source_type: str, company_name: str, evidence_list) -> tuple[str, str]:
    """Build Stage A system + user prompt for a specific source type."""
    evidence_block = build_evidence_block(evidence_list)
    user = STAGE_A_USER.format(
        source_type=source_type,
        company_name=company_name,
        evidence_block=evidence_block,
    )
    return STAGE_A_SYSTEM, user


def build_stage_b_prompt(
    company_name: str,
    stage_a_results: list[dict],
    limitations: list[str],
    research_question: str = None,
) -> tuple[str, str]:
    """Build Stage B system + user prompt from Stage A outputs."""
    import json
    stage_a_block = json.dumps(stage_a_results, indent=2)
    limitations_block = "\n".join(f"- {lim}" for lim in limitations) if limitations else "None"
    research_question_block = f"Research question: {research_question}" if research_question else ""

    user = STAGE_B_USER.format(
        company_name=company_name,
        stage_a_block=stage_a_block,
        limitations_block=limitations_block,
        research_question_block=research_question_block,
    )
    return STAGE_B_SYSTEM, user
