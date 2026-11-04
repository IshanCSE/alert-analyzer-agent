"""Pytest configuration and fixtures."""

import pytest
from pathlib import Path
from unittest.mock import Mock

from ai_alert.config import Config, SlackConfig, SentryConfig, ClaudeConfig
from ai_alert.models import Alert, Analysis, Recommendation, AlertStatus


@pytest.fixture
def config() -> Config:
    """Fixture: Default test configuration."""
    return Config(
        slack=SlackConfig(channel="test-channel"),
        sentry=SentryConfig(organization="test-org", project="test-project"),
        claude=ClaudeConfig(model="claude-sonnet-5-5", effort="medium"),
    )


@pytest.fixture
def test_alert() -> Alert:
    """Fixture: Sample alert for testing."""
    return Alert(
        sentry_issue_id="12345",
        sentry_url="https://sentry.io/organizations/test/issues/12345/",
        title="Test Error: NullPointerException",
        slack_channel="test-channel",
        slack_message_ts="1234567890.123456",
        status=AlertStatus.PENDING,
    )


@pytest.fixture
def test_recommendation() -> Recommendation:
    """Fixture: Sample recommendation for testing."""
    return Recommendation(
        summary="NullPointerException in alerts collector",
        suggested_fix="Add null check before accessing field",
        files_to_inspect=["internal/collector/alerts/alerts.go"],
        related_code_paths=["internal/collector/alerts/alerts_count.go"],
        follow_up_actions=[
            "Review recent changes to alerts collector",
            "Add unit test for null case",
        ],
        is_known_issue=False,
    )


@pytest.fixture
def test_analysis(test_alert: Alert, test_recommendation: Recommendation) -> Analysis:
    """Fixture: Sample analysis for testing."""
    return Analysis(
        alert_id=test_alert.id,
        sentry_issue_id=test_alert.sentry_issue_id,
        model="claude-sonnet-5-5",
        root_cause="Missing null check in alerts collector caused NullPointerException",
        confidence="high",
        error_category="api_error",
        affected_component="alerts-count-collector",
        recommendation=test_recommendation,
        tokens_used=1250,
    )


@pytest.fixture
def mock_sentry_fetcher():
    """Fixture: Mock SentryFetcher for testing."""
    fetcher = Mock()
    fetcher.get_issue.return_value = {
        "id": "12345",
        "title": "Test Error",
        "status": "unresolved",
    }
    fetcher.get_latest_event.return_value = {
        "event_id": "event-123",
        "exception": {
            "values": [
                {
                    "type": "NullPointerException",
                    "value": "null pointer",
                    "stacktrace": {
                        "frames": [
                            {
                                "filename": "internal/collector/alerts/alerts.go",
                                "lineno": 42,
                                "function": "FetchAlerts",
                            }
                        ]
                    },
                }
            ]
        },
        "tags": {
            "pod": "cx-collector-12345",
            "release": "v1.2.3",
        },
    }
    return fetcher


@pytest.fixture
def mock_claude_client():
    """Fixture: Mock ClaudeClient for testing."""
    client = Mock()
    client.analyze.return_value = (
        Recommendation(
            summary="Test recommendation",
            suggested_fix="Apply this fix",
            files_to_inspect=["test.go"],
            related_code_paths=["related.go"],
            follow_up_actions=["Action 1"],
            is_known_issue=False,
        ),
        1500,  # tokens_used
    )
    return client


@pytest.fixture
def mock_store():
    """Fixture: Mock Store for testing."""
    store = Mock()
    store.get_alert_by_sentry_id.return_value = None
    store.save_alert.return_value = None
    store.save_analysis.return_value = None
    return store


@pytest.fixture
def mock_sentry_fetcher_instance(mock_sentry_fetcher):
    """Fixture: Real SentryFetcher-like mock for direct usage."""
    # This allows tests to use the mock_sentry_fetcher from conftest
    # while also allowing patching in individual tests
    return mock_sentry_fetcher
