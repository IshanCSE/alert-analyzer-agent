"""Tests for CLI commands (Phase 8)."""

import pytest
from click.testing import CliRunner
from pathlib import Path
from unittest.mock import Mock, patch

from ai_alert.cli import main, list as list_cmd, show as show_cmd, gc as gc_cmd
from ai_alert.models import Alert, Analysis, Recommendation, AlertStatus


@pytest.fixture
def cli_runner():
    """Fixture: Click CLI runner."""
    return CliRunner()


@pytest.fixture
def mock_config(tmp_path):
    """Fixture: Mock config file."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
slack:
  channel: test-alerts
sentry:
  organization: test-org
  project: test-project
claude:
  model: claude-sonnet-5-5
  effort: medium
cloudwatch:
  enabled: true
  region: us-west-2
storage:
  db_path: {}
logging:
  dir: {}
""".format(str(tmp_path / "test.db"), str(tmp_path / "logs")))
    return str(config_file)


# LIST COMMAND


class TestListCommand:
    def test_list_no_alerts(self, cli_runner, mock_config):
        """Test list command with no alerts."""
        with patch("ai_alert.cli.Store") as mock_store_cls:
            mock_store = Mock()
            mock_store.__enter__ = Mock(return_value=mock_store)
            mock_store.__exit__ = Mock(return_value=None)
            mock_store.list_alerts.return_value = []
            mock_store_cls.return_value = mock_store

            result = cli_runner.invoke(list_cmd, ["--config", mock_config])

            assert result.exit_code == 0
            assert "No alerts found" in result.output

    def test_list_with_alerts(self, cli_runner, mock_config):
        """Test list command with multiple alerts."""
        alert1 = Alert(
            sentry_issue_id="12345",
            sentry_url="https://sentry.io/issues/12345/",
            title="Test Error 1",
            slack_channel="test-alerts",
            status=AlertStatus.PENDING,
        )
        alert2 = Alert(
            sentry_issue_id="67890",
            sentry_url="https://sentry.io/issues/67890/",
            title="Test Error 2",
            slack_channel="test-alerts",
            status=AlertStatus.ANALYZED,
        )

        with patch("ai_alert.cli.Store") as mock_store_cls:
            mock_store = Mock()
            mock_store.__enter__ = Mock(return_value=mock_store)
            mock_store.__exit__ = Mock(return_value=None)
            mock_store.list_alerts.return_value = [alert1, alert2]
            mock_store_cls.return_value = mock_store

            result = cli_runner.invoke(list_cmd, ["--config", mock_config])

            assert result.exit_code == 0
            assert "12345" in result.output
            assert "67890" in result.output
            assert "Test Error 1" in result.output
            assert "Test Error 2" in result.output

    def test_list_filtered_by_status(self, cli_runner, mock_config):
        """Test list command filtered by status."""
        with patch("ai_alert.cli.Store") as mock_store_cls:
            mock_store = Mock()
            mock_store.__enter__ = Mock(return_value=mock_store)
            mock_store.__exit__ = Mock(return_value=None)
            mock_store.list_alerts.return_value = []
            mock_store_cls.return_value = mock_store

            result = cli_runner.invoke(list_cmd, [
                "--status", "pending",
                "--config", mock_config,
            ])

            assert result.exit_code == 0
            # Verify list_alerts was called with status filter
            call_kwargs = mock_store.list_alerts.call_args[1]
            assert call_kwargs["status"] == "pending"


# SHOW COMMAND


class TestShowCommand:
    def test_show_nonexistent_alert(self, cli_runner, mock_config):
        """Test show command for nonexistent alert."""
        with patch("ai_alert.cli.Store") as mock_store_cls:
            mock_store = Mock()
            mock_store.__enter__ = Mock(return_value=mock_store)
            mock_store.__exit__ = Mock(return_value=None)
            mock_store.get_alert_by_id.return_value = None
            mock_store_cls.return_value = mock_store

            result = cli_runner.invoke(show_cmd, ["abc123", "--config", mock_config])

            assert result.exit_code == 1
            assert "not found" in result.output

    def test_show_alert_without_analysis(self, cli_runner, mock_config):
        """Test show command for alert without analysis."""
        alert = Alert(
            id="abc123",
            sentry_issue_id="12345",
            sentry_url="https://sentry.io/issues/12345/",
            title="Test Error",
            slack_channel="test-alerts",
            status=AlertStatus.PENDING,
        )

        with patch("ai_alert.cli.Store") as mock_store_cls:
            mock_store = Mock()
            mock_store.__enter__ = Mock(return_value=mock_store)
            mock_store.__exit__ = Mock(return_value=None)
            mock_store.get_alert_by_id.return_value = alert
            mock_store.get_analysis_by_alert_id.return_value = None
            mock_store_cls.return_value = mock_store

            result = cli_runner.invoke(show_cmd, ["abc123", "--config", mock_config])

            assert result.exit_code == 0
            assert "12345" in result.output
            assert "Test Error" in result.output
            assert "No analysis yet" in result.output

    def test_show_alert_with_analysis(self, cli_runner, mock_config):
        """Test show command for alert with analysis."""
        alert = Alert(
            id="abc123",
            sentry_issue_id="12345",
            sentry_url="https://sentry.io/issues/12345/",
            title="Test Error",
            slack_channel="test-alerts",
            status=AlertStatus.ANALYZED,
        )

        analysis = Analysis(
            alert_id="abc123",
            sentry_issue_id="12345",
            model="claude-sonnet-5-5",
            root_cause="Null pointer dereference",
            confidence="high",
            error_category="api_error",
            affected_component="alerts",
            recommendation=Recommendation(
                summary="Add null check",
                suggested_fix="Check for nil before accessing",
                files_to_inspect=["alerts.go"],
                related_code_paths=["internal/collector/"],
                follow_up_actions=["review", "test"],
                is_known_issue=False,
            ),
            tokens_used=450,
        )

        with patch("ai_alert.cli.Store") as mock_store_cls:
            mock_store = Mock()
            mock_store.__enter__ = Mock(return_value=mock_store)
            mock_store.__exit__ = Mock(return_value=None)
            mock_store.get_alert_by_id.return_value = alert
            mock_store.get_analysis_by_alert_id.return_value = analysis
            mock_store_cls.return_value = mock_store

            result = cli_runner.invoke(show_cmd, ["abc123", "--config", mock_config])

            assert result.exit_code == 0
            assert "Test Error" in result.output
            assert "Null pointer dereference" in result.output
            assert "Add null check" in result.output
            assert "alerts.go" in result.output


# GC COMMAND


class TestGcCommand:
    def test_gc_no_old_alerts(self, cli_runner, mock_config):
        """Test gc command with no old alerts."""
        with patch("ai_alert.cli.Store") as mock_store_cls:
            mock_store = Mock()
            mock_store.__enter__ = Mock(return_value=mock_store)
            mock_store.__exit__ = Mock(return_value=None)
            mock_store.list_alerts.return_value = []
            mock_store_cls.return_value = mock_store

            result = cli_runner.invoke(gc_cmd, ["--config", mock_config])

            assert result.exit_code == 0
            assert "No alerts" in result.output

    def test_gc_dry_run(self, cli_runner, mock_config):
        """Test gc command in dry-run mode."""
        from datetime import datetime, timedelta

        old_alert = Alert(
            id="old123",
            sentry_issue_id="12345",
            sentry_url="https://sentry.io/issues/12345/",
            title="Old Error",
            slack_channel="test-alerts",
            received_at=datetime.utcnow() - timedelta(days=60),
        )

        with patch("ai_alert.cli.Store") as mock_store_cls:
            mock_store = Mock()
            mock_store.__enter__ = Mock(return_value=mock_store)
            mock_store.__exit__ = Mock(return_value=None)
            mock_store.list_alerts.return_value = [old_alert]
            mock_store_cls.return_value = mock_store

            result = cli_runner.invoke(gc_cmd, [
                "--days", "30",
                "--dry-run",
                "--config", mock_config,
            ])

            assert result.exit_code == 0
            assert "DRY RUN" in result.output
            assert "Would delete" in result.output
            # Should not call delete_alert in dry-run mode
            mock_store.delete_alert.assert_not_called()

    def test_gc_actually_deletes(self, cli_runner, mock_config):
        """Test gc command actually deletes without dry-run."""
        from datetime import datetime, timedelta

        old_alert = Alert(
            id="old123",
            sentry_issue_id="12345",
            sentry_url="https://sentry.io/issues/12345/",
            title="Old Error",
            slack_channel="test-alerts",
            received_at=datetime.utcnow() - timedelta(days=60),
        )

        with patch("ai_alert.cli.Store") as mock_store_cls:
            mock_store = Mock()
            mock_store.__enter__ = Mock(return_value=mock_store)
            mock_store.__exit__ = Mock(return_value=None)
            mock_store.list_alerts.return_value = [old_alert]
            mock_store_cls.return_value = mock_store

            result = cli_runner.invoke(gc_cmd, [
                "--days", "30",
                "--config", mock_config,
            ])

            assert result.exit_code == 0
            assert "Deleted" in result.output
            # Should call delete_alert
            mock_store.delete_alert.assert_called_once()


# MAIN COMMAND


class TestMainCommand:
    def test_main_help(self, cli_runner):
        """Test main help command."""
        result = cli_runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "AI Alert Agent" in result.output

    def test_main_version(self, cli_runner):
        """Test main version command."""
        result = cli_runner.invoke(main, ["--version"])

        assert result.exit_code == 0
        # Should show version (0.1.0 or similar)
        assert "0." in result.output
