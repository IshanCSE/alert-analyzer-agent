"""Tests for data models."""

import pytest
from datetime import datetime

from ai_alert.models import Alert, Analysis, Recommendation, AlertStatus, CodeSnippet


def test_alert_creation():
    """Test Alert model creation."""
    alert = Alert(
        sentry_issue_id="12345",
        sentry_url="https://sentry.io/issues/12345/",
        title="Test Error",
        slack_channel="test-channel",
    )

    assert alert.sentry_issue_id == "12345"
    assert alert.status == AlertStatus.PENDING
    assert alert.id is not None
    assert isinstance(alert.received_at, datetime)


def test_alert_status_enum():
    """Test AlertStatus enum values."""
    assert AlertStatus.PENDING.value == "pending"
    assert AlertStatus.ANALYZING.value == "analyzing"
    assert AlertStatus.ANALYZED.value == "analyzed"
    assert AlertStatus.FAILED.value == "failed"


def test_code_snippet_creation():
    """Test CodeSnippet model creation."""
    snippet = CodeSnippet(
        file_path="internal/collector/alerts/alerts.go",
        line_number=42,
        context="def fetch_alerts():\n    pass",
    )

    assert snippet.file_path == "internal/collector/alerts/alerts.go"
    assert snippet.line_number == 42


def test_recommendation_creation(test_recommendation):
    """Test Recommendation model creation."""
    assert test_recommendation.summary == "NullPointerException in alerts collector"
    assert test_recommendation.is_known_issue is False
    assert len(test_recommendation.follow_up_actions) > 0


def test_analysis_creation(test_analysis):
    """Test Analysis model creation."""
    assert test_analysis.model == "claude-sonnet-5-5"
    assert test_analysis.confidence == "high"
    assert test_analysis.tokens_used == 1250
    assert isinstance(test_analysis.created_at, datetime)


def test_analysis_json_serialization(test_analysis):
    """Test that Analysis can be serialized to JSON."""
    json_str = test_analysis.model_dump_json()
    assert "root_cause" in json_str
    assert "recommendation" in json_str
