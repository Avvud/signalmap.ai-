from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class PipelineStatus(str, Enum):
    QUEUED = "queued"
    FETCHING_SOURCES = "fetching_sources"
    NORMALIZING = "normalizing"
    ANALYZING = "analyzing"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    FAILED = "failed"


class ResearchMode(str, Enum):
    FULL = "full"
    CONTENT = "content"
    DEVELOPER = "developer"
    MESSAGING = "messaging"


class SourceType(str, Enum):
    WEBSITE = "website"
    YOUTUBE = "youtube"
    REDDIT = "reddit"
    GITHUB = "github"


class ClaimType(str, Enum):
    OBSERVATION = "observation"
    INTERPRETATION = "interpretation"
    HYPOTHESIS = "hypothesis"


class ResearchInput(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=200)
    website_url: Optional[str] = None
    research_question: Optional[str] = None
    mode: ResearchMode = ResearchMode.FULL


class RunStatusResponse(BaseModel):
    run_id: str
    company_name: str
    website_url: Optional[str] = None
    research_question: Optional[str] = None
    mode: ResearchMode
    status: PipelineStatus
    error_message: Optional[str] = None
    created_at: str
    updated_at: str


class Evidence(BaseModel):
    evidence_id: str
    run_id: str
    source: SourceType
    source_url: str
    title: str
    raw_content: str
    normalized_content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class WebsiteEvidence(Evidence):
    source: SourceType = SourceType.WEBSITE


class YouTubeEvidence(Evidence):
    source: SourceType = SourceType.YOUTUBE


class RedditEvidence(Evidence):
    source: SourceType = SourceType.REDDIT


class GitHubEvidence(Evidence):
    source: SourceType = SourceType.GITHUB


class Finding(BaseModel):
    id: str
    run_id: str
    claim: str
    claim_type: ClaimType
    evidence_ids: list[str]
    confidence: float
    source_category: str


class SourceBreakdown(BaseModel):
    source: SourceType
    items_collected: int
    status: str
    error: Optional[str] = None


class ResearchReport(BaseModel):
    id: str
    run_id: str
    company_name: str
    executive_summary: str
    findings: list[Finding]
    cross_platform_findings: str
    opportunity: str
    source_breakdown: list[SourceBreakdown]
    limitations: list[str]
    created_at: str
