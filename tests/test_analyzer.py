"""Tests for Analyzer orchestrator (Phase 4-6)."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import os

from ai_alert.services.analyzer import Analyzer
from ai_alert.services.codebase_analyzer import CodebaseAnalyzer
from ai_alert.services.cloudwatch_fetcher import CloudWatchFetcher
from ai_alert.models import Alert, AlertStatus, Recommendation
from ai_alert.config import Config, SlackConfig, SentryConfig, ClaudeConfig


@pytest.fixture
def config():
    """Fixture: Test configuration."""
    return Config(
        slack=SlackConfig(channel="test-alerts"),
        sentry=SentryConfig(organization="test-org", project="test-project"),
        claude=ClaudeConfig(model="claude-sonnet-5-5", effort="medium"),
    )


@pytest.fixture
def mock_store():
    """Fixture: Mocked Store."""
    store = Mock()
    store.get_alert_by_sentry_id.return_value = None
    store.save_alert.return_value = None
    store.save_analysis.return_value = None
    store.update_alert_status.return_value = None
    store.get_analysis_by_alert_id.return_value = None
    store.get_stats.return_value = {
        "total_alerts": 0,
        "pending": 0,
        "analyzing": 0,
        "analyzed": 0,
        "failed": 0,
        "total_analyses": 0,
    }
    store.list_alerts.return_value = []
    return store


@pytest.fixture
def mock_sentry_fetcher():
    """Fixture: Mocked SentryFetcher."""
    fetcher = Mock()
    fetcher.get_issue.return_value = {
        "id": "12345",
        "title": "Test Error",
        "url": "https://sentry.io/issues/12345/",
    }
    fetcher.get_latest_event.return_value = {
        "event_id": "evt-123",
        "exception": {
            "values": [
                {
                    "type": "NullPointerException",
                    "value": "null pointer",
                    "stacktrace": {"frames": []},
                }
            ]
        },
    }
    return fetcher


@pytest.fixture
def mock_claude_client():
    """Fixture: Mocked ClaudeClient."""
    client = Mock()
    client.model = "claude-sonnet-5-5"
    client.analyze.return_value = (
        Recommendation(
            summary="Test root cause",
            suggested_fix="Apply fix",
            files_to_inspect=["test.go"],
            related_code_paths=["lib/"],
            follow_up_actions=["review"],
            is_known_issue=False,
        ),
        500,  # tokens
    )
    return client


@pytest.fixture
def mock_codebase_analyzer():
    """Fixture: Mocked CodebaseAnalyzer."""
    analyzer = Mock(spec=CodebaseAnalyzer)
    analyzer.extract_snippet.return_value = "    line 42: code snippet here\n    line 43: more code"
    analyzer.find_related_files.return_value = ["internal/collector/alerts/alerts.go"]
    analyzer.find_test_files.return_value = ["internal/collector/alerts/alerts_test.go"]
    return analyzer


@pytest.fixture
def mock_cloudwatch_fetcher():
    """Fixture: Mocked CloudWatchFetcher."""
    fetcher = Mock(spec=CloudWatchFetcher)
    fetcher.extract_pod_from_tags.return_value = "cx-collector-pod-123"
    fetcher.query_pod_logs.return_value = "2024-10-29 15:00:00 ERROR: null pointer\n2024-10-29 15:00:01 Pod restarting"
    return fetcher


# INITIALIZATION


class TestAnalyzerInitialization:
    def test_init_with_provided_clients(self, config, mock_store, mock_sentry_fetcher, mock_claude_client):
        """Test Analyzer initialization with provided clients."""
        analyzer = Analyzer(
            config=config,
            store=mock_store,
            sentry_fetcher=mock_sentry_fetcher,
            claude_client=mock_claude_client,
        )

        assert analyzer.config == config
        assert analyzer.store == mock_store
        assert analyzer.sentry_fetcher == mock_sentry_fetcher
        assert analyzer.claude_client == mock_claude_client

    def test_init_without_sentry_fetcher_raises(self, config, mock_store, mock_claude_client):
        """Test Analyzer raises without SENTRY_API_TOKEN when not provided."""
        # Clear environment
        if "SENTRY_API_TOKEN" in os.environ:
            del os.environ["SENTRY_API_TOKEN"]

        with pytest.raises(ValueError, match="SENTRY_API_TOKEN"):
            Analyzer(
                config=config,
                store=mock_store,
                claude_client=mock_claude_client,
            )

    def test_init_without_claude_client_raises(self, config, mock_store, mock_sentry_fetcher):
        """Test Analyzer raises without ANTHROPIC_API_KEY when not provided."""
        # Clear environment
        if "ANTHROPIC_API_KEY" in os.environ:
            del os.environ["ANTHROPIC_API_KEY"]

        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            Analyzer(
                config=config,
                store=mock_store,
                sentry_fetcher=mock_sentry_fetcher,
            )


# ANALYZE_ALERT METHOD


class TestAnalyzeAlert:
    def test_analyze_alert_full_workflow(
        self, config, mock_store, mock_sentry_fetcher, mock_claude_client
    ):
        """Test full analysis workflow."""
        # Setup: alert doesn't exist yet
        mock_store.get_alert_by_sentry_id.return_value = None

        analyzer = Analyzer(
            config=config,
            store=mock_store,
            sentry_fetcher=mock_sentry_fetcher,
            claude_client=mock_claude_client,
        )

        result = analyzer.analyze_alert(sentry_issue_id="12345")

        # Verify workflow steps
        assert mock_sentry_fetcher.get_issue.called
        assert mock_sentry_fetcher.get_latest_event.called
        assert mock_claude_client.analyze.called
        assert mock_store.save_alert.called
        assert mock_store.save_analysis.called
        assert mock_store.update_alert_status.called

        # Verify result
        assert result is not None

    def test_analyze_alert_skips_already_analyzed(
        self, config, mock_store, mock_sentry_fetcher, mock_claude_client
    ):
        """Test that already-analyzed alerts are skipped (unless force=True)."""
        # Setup: alert exists and is analyzed
        existing_alert = Alert(
            sentry_issue_id="12345",
            sentry_url="url",
            title="Test",
            slack_channel="test",
            status=AlertStatus.ANALYZED,
        )
        mock_store.get_alert_by_sentry_id.return_value = existing_alert
        existing_analysis = Mock()
        mock_store.get_analysis_by_alert_id.return_value = existing_analysis

        analyzer = Analyzer(
            config=config,
            store=mock_store,
            sentry_fetcher=mock_sentry_fetcher,
            claude_client=mock_claude_client,
        )

        result = analyzer.analyze_alert(sentry_issue_id="12345", force=False)

        # Should not call Claude
        assert not mock_claude_client.analyze.called
        # Should return existing analysis
        assert result == existing_analysis

    def test_analyze_alert_forces_reanalysis(
        self, config, mock_store, mock_sentry_fetcher, mock_claude_client
    ):
        """Test force=True re-analyzes even if already analyzed."""
        existing_alert = Alert(
            sentry_issue_id="12345",
            sentry_url="url",
            title="Test",
            slack_channel="test",
            status=AlertStatus.ANALYZED,
        )
        mock_store.get_alert_by_sentry_id.return_value = existing_alert

        analyzer = Analyzer(
            config=config,
            store=mock_store,
            sentry_fetcher=mock_sentry_fetcher,
            claude_client=mock_claude_client,
        )

        analyzer.analyze_alert(sentry_issue_id="12345", force=True)

        # Should call Claude despite existing analysis
        assert mock_claude_client.analyze.called

    def test_analyze_alert_dry_run(
        self, config, mock_store, mock_sentry_fetcher, mock_claude_client
    ):
        """Test dry_run gathers evidence but doesn't call Claude."""
        mock_store.get_alert_by_sentry_id.return_value = None

        analyzer = Analyzer(
            config=config,
            store=mock_store,
            sentry_fetcher=mock_sentry_fetcher,
            claude_client=mock_claude_client,
        )

        result = analyzer.analyze_alert(sentry_issue_id="12345", dry_run=True)

        # Should not call Claude
        assert not mock_claude_client.analyze.called
        # Should not save analysis
        assert not mock_store.save_analysis.called
        # Should return None
        assert result is None

    def test_analyze_alert_sentry_fetch_fails(
        self, config, mock_store, mock_sentry_fetcher, mock_claude_client
    ):
        """Test handling when Sentry fetch fails."""
        mock_store.get_alert_by_sentry_id.return_value = None
        mock_sentry_fetcher.get_issue.return_value = None

        analyzer = Analyzer(
            config=config,
            store=mock_store,
            sentry_fetcher=mock_sentry_fetcher,
            claude_client=mock_claude_client,
        )

        result = analyzer.analyze_alert(sentry_issue_id="12345")

        # Should return None and not call Claude
        assert result is None
        assert not mock_claude_client.analyze.called

    def test_analyze_alert_claude_error_updates_status(
        self, config, mock_store, mock_sentry_fetcher, mock_claude_client
    ):
        """Test that Claude errors update alert status to FAILED."""
        mock_store.get_alert_by_sentry_id.return_value = None
        mock_claude_client.analyze.side_effect = ValueError("API error")

        analyzer = Analyzer(
            config=config,
            store=mock_store,
            sentry_fetcher=mock_sentry_fetcher,
            claude_client=mock_claude_client,
        )

        with pytest.raises(ValueError):
            analyzer.analyze_alert(sentry_issue_id="12345")

        # Should call update_alert_status to mark as FAILED
        assert mock_store.update_alert_status.called
        # Verify it was called with failure status
        call_kwargs_list = [call[1] if call[1] else {} for call in mock_store.update_alert_status.call_args_list]
        call_args_list = [call[0] for call in mock_store.update_alert_status.call_args_list]
        # Check last call has 'failed' status
        assert any("failed" in str(call) for call in call_args_list)


# LIST & STATS METHODS


class TestAnalyzerListAndStats:
    def test_list_pending_alerts(self, config, mock_store, mock_sentry_fetcher, mock_claude_client):
        """Test listing pending alerts."""
        pending_alerts = [
            Alert(sentry_issue_id="1", sentry_url="u", title="t", slack_channel="c"),
            Alert(sentry_issue_id="2", sentry_url="u", title="t", slack_channel="c"),
        ]
        mock_store.list_alerts.return_value = pending_alerts

        analyzer = Analyzer(
            config=config,
            store=mock_store,
            sentry_fetcher=mock_sentry_fetcher,
            claude_client=mock_claude_client,
        )

        result = analyzer.list_pending_alerts(limit=10)

        assert len(result) == 2
        mock_store.list_alerts.assert_called_once()

    def test_get_statistics(self, config, mock_store, mock_sentry_fetcher, mock_claude_client):
        """Test getting statistics."""
        mock_store.get_stats.return_value = {
            "total_alerts": 10,
            "pending": 3,
            "analyzing": 1,
            "analyzed": 5,
            "failed": 1,
            "total_analyses": 5,
        }

        analyzer = Analyzer(
            config=config,
            store=mock_store,
            sentry_fetcher=mock_sentry_fetcher,
            claude_client=mock_claude_client,
        )

        stats = analyzer.get_statistics()

        assert stats["total_alerts"] == 10
        assert stats["pending"] == 3
        assert stats["analyzed"] == 5


# CLOUDWATCH LOGS GATHERING (Phase 6)


class TestCloudWatchLogsGathering:
    def test_gather_cloudwatch_logs_with_tags(
        self, config, mock_store, mock_sentry_fetcher, mock_claude_client, mock_cloudwatch_fetcher
    ):
        """Test CloudWatch logs gathering from pod ID."""
        analyzer = Analyzer(
            config=config,
            store=mock_store,
            sentry_fetcher=mock_sentry_fetcher,
            claude_client=mock_claude_client,
            cloudwatch_fetcher=mock_cloudwatch_fetcher,
        )

        sentry_event = {
            "tags": {"pod": "cx-collector-pod-123", "environment": "prod"},
            "timestamp": "2024-10-29T15:00:00Z",
        }

        logs = analyzer._gather_cloudwatch_logs(sentry_event, "12345")

        assert logs != ""
        assert "ERROR" in logs
        assert mock_cloudwatch_fetcher.extract_pod_from_tags.called
        assert mock_cloudwatch_fetcher.query_pod_logs.called

    def test_gather_cloudwatch_logs_no_pod_id(
        self, config, mock_store, mock_sentry_fetcher, mock_claude_client, mock_cloudwatch_fetcher
    ):
        """Test CloudWatch logs gathering with no pod ID."""
        mock_cloudwatch_fetcher.extract_pod_from_tags.return_value = None

        analyzer = Analyzer(
            config=config,
            store=mock_store,
            sentry_fetcher=mock_sentry_fetcher,
            claude_client=mock_claude_client,
            cloudwatch_fetcher=mock_cloudwatch_fetcher,
        )

        sentry_event = {"tags": {}, "timestamp": "2024-10-29T15:00:00Z"}

        logs = analyzer._gather_cloudwatch_logs(sentry_event, "12345")

        assert logs == ""
        assert not mock_cloudwatch_fetcher.query_pod_logs.called

    def test_gather_cloudwatch_logs_no_fetcher(
        self, config, mock_store, mock_sentry_fetcher, mock_claude_client
    ):
        """Test CloudWatch logs gathering without CloudWatchFetcher."""
        analyzer = Analyzer(
            config=config,
            store=mock_store,
            sentry_fetcher=mock_sentry_fetcher,
            claude_client=mock_claude_client,
            cloudwatch_fetcher=None,
        )

        sentry_event = {"tags": {"pod": "test-pod"}, "timestamp": "2024-10-29T15:00:00Z"}

        logs = analyzer._gather_cloudwatch_logs(sentry_event, "12345")

        assert logs == ""

    def test_analyze_alert_with_cloudwatch_logs(
        self, config, mock_store, mock_sentry_fetcher, mock_claude_client, mock_cloudwatch_fetcher
    ):
        """Test analyze_alert includes CloudWatch logs in Claude call."""
        mock_store.get_alert_by_sentry_id.return_value = None

        analyzer = Analyzer(
            config=config,
            store=mock_store,
            sentry_fetcher=mock_sentry_fetcher,
            claude_client=mock_claude_client,
            cloudwatch_fetcher=mock_cloudwatch_fetcher,
        )

        # Mock Sentry response with pod tags and timestamp
        mock_sentry_fetcher.get_latest_event.return_value = {
            "tags": {"pod": "cx-collector-prod"},
            "timestamp": "2024-10-29T15:00:00Z",
            "exception": {"values": []},
        }

        result = analyzer.analyze_alert(sentry_issue_id="12345")

        # Verify Claude was called
        assert mock_claude_client.analyze.called

        # Verify CloudWatch was queried
        assert mock_cloudwatch_fetcher.query_pod_logs.called


# CODE CONTEXT GATHERING (Phase 5)


class TestCodeContextGathering:
    def test_gather_code_context_with_frames(
        self, config, mock_store, mock_sentry_fetcher, mock_claude_client, mock_codebase_analyzer
    ):
        """Test code context gathering from stack frames."""
        analyzer = Analyzer(
            config=config,
            store=mock_store,
            sentry_fetcher=mock_sentry_fetcher,
            claude_client=mock_claude_client,
            codebase_analyzer=mock_codebase_analyzer,
        )

        sentry_event = {
            "exception": {
                "values": [
                    {
                        "stacktrace": {
                            "frames": [
                                {
                                    "filename": "internal/collector/alerts/alerts.go",
                                    "lineno": 42,
                                    "in_app": True,
                                }
                            ]
                        }
                    }
                ]
            }
        }

        context = analyzer._gather_code_context(sentry_event)

        assert context != ""
        assert "alerts.go:42" in context
        assert mock_codebase_analyzer.extract_snippet.called

    def test_gather_code_context_without_frames(
        self, config, mock_store, mock_sentry_fetcher, mock_claude_client, mock_codebase_analyzer
    ):
        """Test code context gathering with empty exception."""
        analyzer = Analyzer(
            config=config,
            store=mock_store,
            sentry_fetcher=mock_sentry_fetcher,
            claude_client=mock_claude_client,
            codebase_analyzer=mock_codebase_analyzer,
        )

        sentry_event = {"exception": {"values": []}}

        context = analyzer._gather_code_context(sentry_event)

        assert context == ""
        assert not mock_codebase_analyzer.extract_snippet.called

    def test_gather_code_context_no_analyzer(
        self, config, mock_store, mock_sentry_fetcher, mock_claude_client
    ):
        """Test code context gathering without CodebaseAnalyzer."""
        analyzer = Analyzer(
            config=config,
            store=mock_store,
            sentry_fetcher=mock_sentry_fetcher,
            claude_client=mock_claude_client,
            codebase_analyzer=None,
        )

        sentry_event = {
            "exception": {
                "values": [{"stacktrace": {"frames": [{"filename": "test.go", "lineno": 10}]}}]
            }
        }

        context = analyzer._gather_code_context(sentry_event)

        assert context == ""

    def test_analyze_alert_with_code_context(
        self, config, mock_store, mock_sentry_fetcher, mock_claude_client, mock_codebase_analyzer
    ):
        """Test analyze_alert includes code context in Claude call."""
        mock_store.get_alert_by_sentry_id.return_value = None

        analyzer = Analyzer(
            config=config,
            store=mock_store,
            sentry_fetcher=mock_sentry_fetcher,
            claude_client=mock_claude_client,
            codebase_analyzer=mock_codebase_analyzer,
        )

        # Mock Sentry response with frames
        mock_sentry_fetcher.get_latest_event.return_value = {
            "exception": {
                "values": [
                    {
                        "stacktrace": {
                            "frames": [
                                {
                                    "filename": "internal/collector/alerts/alerts.go",
                                    "lineno": 42,
                                    "in_app": True,
                                }
                            ]
                        }
                    }
                ]
            }
        }

        result = analyzer.analyze_alert(sentry_issue_id="12345")

        # Verify Claude was called
        assert mock_claude_client.analyze.called

        # Verify code context was passed to Claude
        call_args = mock_claude_client.analyze.call_args
        user_prompt = call_args[1]["user_prompt"]
        assert "alerts.go" in user_prompt or "code snippet" in user_prompt


# CLEANUP


class TestAnalyzerCleanup:
    def test_close_closes_resources(
        self, config, mock_store, mock_sentry_fetcher, mock_claude_client
    ):
        """Test that close() closes all resources."""
        analyzer = Analyzer(
            config=config,
            store=mock_store,
            sentry_fetcher=mock_sentry_fetcher,
            claude_client=mock_claude_client,
        )

        analyzer.close()

        assert mock_sentry_fetcher.close.called
        assert mock_store.close.called

    def test_close_closes_codebase_analyzer(
        self, config, mock_store, mock_sentry_fetcher, mock_claude_client, mock_codebase_analyzer
    ):
        """Test that close() closes CodebaseAnalyzer."""
        analyzer = Analyzer(
            config=config,
            store=mock_store,
            sentry_fetcher=mock_sentry_fetcher,
            claude_client=mock_claude_client,
            codebase_analyzer=mock_codebase_analyzer,
        )

        analyzer.close()

        assert mock_sentry_fetcher.close.called
        assert mock_codebase_analyzer.close.called
        assert mock_store.close.called

    def test_close_closes_cloudwatch_fetcher(
        self, config, mock_store, mock_sentry_fetcher, mock_claude_client, mock_cloudwatch_fetcher
    ):
        """Test that close() closes CloudWatchFetcher."""
        analyzer = Analyzer(
            config=config,
            store=mock_store,
            sentry_fetcher=mock_sentry_fetcher,
            claude_client=mock_claude_client,
            cloudwatch_fetcher=mock_cloudwatch_fetcher,
        )

        analyzer.close()

        assert mock_sentry_fetcher.close.called
        assert mock_cloudwatch_fetcher.close.called
        assert mock_store.close.called
