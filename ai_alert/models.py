"""Data models for AI Alert Agent."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, List

from pydantic import BaseModel, Field


class AlertStatus(str, Enum):
    """Status of an alert."""
    PENDING = "pending"
    ANALYZING = "analyzing"
    ANALYZED = "analyzed"
    FAILED = "failed"


class Alert(BaseModel):
    """Represents a Sentry issue received from Slack."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sentry_issue_id: str  # unique key for dedup
    sentry_url: str
    title: str
    slack_channel: str
    slack_message_ts: Optional[str] = None  # for threaded replies
    status: AlertStatus = AlertStatus.PENDING
    received_at: datetime = Field(default_factory=datetime.utcnow)
    last_error: Optional[str] = None


class CodeSnippet(BaseModel):
    """Code context around a stack frame."""
    file_path: str
    line_number: int
    context: str  # ~20 lines surrounding the frame


class Evidence(BaseModel):
    """Collects all gathered context for analysis."""
    sentry_payload: dict  # Full Sentry event JSON
    cloudwatch_logs: Optional[str] = None  # Raw log lines (may be empty)
    code_snippets: List[CodeSnippet] = []
    related_files: List[str] = []


class Recommendation(BaseModel):
    """Structured output from Claude."""
    summary: str
    suggested_fix: str
    files_to_inspect: List[str]
    related_code_paths: List[str]
    follow_up_actions: List[str]
    is_known_issue: bool


class Analysis(BaseModel):
    """Final analysis result from Claude."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_id: str
    sentry_issue_id: str
    model: str  # "claude-sonnet-5-5" etc.
    root_cause: str
    confidence: str  # "low" | "medium" | "high"
    error_category: str  # "api_error" | "parse_error" etc.
    affected_component: str
    recommendation: Recommendation
    tokens_used: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
