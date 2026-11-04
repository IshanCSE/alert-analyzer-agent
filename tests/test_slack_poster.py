"""Tests for SlackPoster (Phase 7)."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from ai_alert.services.slack_poster import SlackPoster
from ai_alert.models import Analysis, Recommendation, AlertStatus


# INITIALIZATION


class TestSlackPosterInitialization:
    def test_init_with_token(self):
        """Test initialization with valid token."""
        poster = SlackPoster(bot_token="xoxb-test-token")
        assert poster.bot_token == "xoxb-test-token"

    def test_init_without_token_raises(self):
        """Test initialization fails without token."""
        with pytest.raises(ValueError, match="bot_token"):
            SlackPoster(bot_token="")

    def test_init_graceful_without_slack_sdk(self):
        """Test initialization gracefully handles missing slack-sdk."""
        poster = SlackPoster(bot_token="xoxb-test")
        assert poster is not None
        # slack_available may be True or False depending on if slack-sdk is installed


# POST REPLY


class TestPostReply:
    def test_post_reply_no_client(self):
        """Test post_reply fails gracefully without client."""
        poster = SlackPoster(bot_token="xoxb-test")
        poster.slack_available = False

        result = poster.post_reply(
            channel="C123",
            thread_ts="1234567890.123456",
            text="Test message",
        )

        assert result == False

    def test_post_reply_missing_params(self):
        """Test post_reply fails without required params."""
        poster = SlackPoster(bot_token="xoxb-test")
        poster.client = Mock()

        result = poster.post_reply(channel="", thread_ts="", text="Test")

        assert result == False
        assert not poster.client.chat_postMessage.called

    def test_post_reply_success(self):
        """Test successful reply posting."""
        poster = SlackPoster(bot_token="xoxb-test")
        mock_client = Mock()
        poster.client = mock_client
        poster.slack_available = True

        mock_client.chat_postMessage.return_value = {"ts": "1234567890.123456"}

        result = poster.post_reply(
            channel="C123",
            thread_ts="1234567890.000000",
            text="Test message",
        )

        assert result == True
        mock_client.chat_postMessage.assert_called_once()

    def test_post_reply_with_blocks(self):
        """Test reply posting with Block Kit blocks."""
        poster = SlackPoster(bot_token="xoxb-test")
        mock_client = Mock()
        poster.client = mock_client
        poster.slack_available = True

        mock_client.chat_postMessage.return_value = {"ts": "1234567890.123456"}

        blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "test"}}]

        result = poster.post_reply(
            channel="C123",
            thread_ts="1234567890.000000",
            text="Test message",
            blocks=blocks,
        )

        assert result == True
        call_args = mock_client.chat_postMessage.call_args
        assert call_args[1]["blocks"] == blocks

    def test_post_reply_exception_handling(self):
        """Test graceful error handling."""
        poster = SlackPoster(bot_token="xoxb-test")
        mock_client = Mock()
        poster.client = mock_client
        poster.slack_available = True

        mock_client.chat_postMessage.side_effect = Exception("API error")

        result = poster.post_reply(
            channel="C123",
            thread_ts="1234567890.000000",
            text="Test message",
        )

        assert result == False


# FORMAT ANALYSIS BLOCKS


class TestFormatAnalysisBlocks:
    def test_format_basic_analysis(self):
        """Test formatting basic analysis object."""
        poster = SlackPoster(bot_token="xoxb-test")

        analysis = Analysis(
            alert_id="a1",
            sentry_issue_id="12345",
            model="claude-sonnet-5-5",
            root_cause="Null pointer dereference",
            confidence="high",
            error_category="api_error",
            affected_component="alerts-collector",
            recommendation=Recommendation(
                summary="Add null check",
                suggested_fix="Check for nil before accessing",
                files_to_inspect=["alerts.go"],
                related_code_paths=["internal/collector/"],
                follow_up_actions=["review", "test"],
                is_known_issue=False,
            ),
            tokens_used=500,
        )

        blocks = poster.format_analysis_blocks(analysis)

        assert len(blocks) > 0
        # Should have sections for summary, fix, files, actions
        assert any("Root Cause" in str(b) for b in blocks)
        assert any("Suggested Fix" in str(b) for b in blocks)

    def test_format_includes_files(self):
        """Test formatting includes files to inspect."""
        poster = SlackPoster(bot_token="xoxb-test")

        analysis = Analysis(
            alert_id="a1",
            sentry_issue_id="12345",
            model="claude-sonnet-5-5",
            root_cause="Test",
            confidence="high",
            error_category="unknown",
            affected_component="test",
            recommendation=Recommendation(
                summary="Test",
                suggested_fix="Fix",
                files_to_inspect=["file1.go", "file2.go"],
                related_code_paths=["lib/"],
                follow_up_actions=[],
                is_known_issue=False,
            ),
            tokens_used=100,
        )

        blocks = poster.format_analysis_blocks(analysis)

        # Should include files section
        assert any("Files to Inspect" in str(b) for b in blocks)

    def test_format_includes_actions(self):
        """Test formatting includes follow-up actions."""
        poster = SlackPoster(bot_token="xoxb-test")

        analysis = Analysis(
            alert_id="a1",
            sentry_issue_id="12345",
            model="claude-sonnet-5-5",
            root_cause="Test",
            confidence="high",
            error_category="unknown",
            affected_component="test",
            recommendation=Recommendation(
                summary="Test",
                suggested_fix="Fix",
                files_to_inspect=[],
                related_code_paths=[],
                follow_up_actions=["review code", "add tests", "monitor"],
                is_known_issue=False,
            ),
            tokens_used=100,
        )

        blocks = poster.format_analysis_blocks(analysis)

        # Should include actions section
        assert any("Follow-up Actions" in str(b) for b in blocks)

    def test_format_includes_metadata(self):
        """Test formatting includes tokens and model info."""
        poster = SlackPoster(bot_token="xoxb-test")

        analysis = Analysis(
            alert_id="a1",
            sentry_issue_id="12345",
            model="claude-opus-5-5",
            root_cause="Test",
            confidence="medium",
            error_category="unknown",
            affected_component="test",
            recommendation=Recommendation(
                summary="Test",
                suggested_fix="Fix",
                files_to_inspect=[],
                related_code_paths=[],
                follow_up_actions=[],
                is_known_issue=False,
            ),
            tokens_used=1234,
        )

        blocks = poster.format_analysis_blocks(analysis)

        # Should include metadata
        assert any("Tokens: 1234" in str(b) for b in blocks)
        assert any("claude-opus-5-5" in str(b) for b in blocks)


# RESOURCE MANAGEMENT


class TestSlackPosterResourceManagement:
    def test_close_method(self):
        """Test close method."""
        poster = SlackPoster(bot_token="xoxb-test")
        poster.client = Mock()

        poster.close()

        assert poster.client is None

    def test_context_manager(self):
        """Test context manager protocol."""
        with SlackPoster(bot_token="xoxb-test") as poster:
            assert poster is not None
        # Should exit cleanly


# INTEGRATION


class TestSlackPosterIntegration:
    def test_full_workflow(self):
        """Test complete workflow: format and post."""
        poster = SlackPoster(bot_token="xoxb-test")
        mock_client = Mock()
        poster.client = mock_client
        poster.slack_available = True

        mock_client.chat_postMessage.return_value = {"ts": "1234567890.123456"}

        # Create analysis
        analysis = Analysis(
            alert_id="a1",
            sentry_issue_id="12345",
            model="claude-sonnet-5-5",
            root_cause="Null pointer",
            confidence="high",
            error_category="api_error",
            affected_component="alerts",
            recommendation=Recommendation(
                summary="Add null check",
                suggested_fix="Check for nil",
                files_to_inspect=["alerts.go"],
                related_code_paths=["internal/"],
                follow_up_actions=["review"],
                is_known_issue=False,
            ),
            tokens_used=450,
        )

        # Format blocks
        blocks = poster.format_analysis_blocks(analysis)
        assert len(blocks) > 0

        # Post reply
        result = poster.post_reply(
            channel="C123",
            thread_ts="1234567890.000000",
            text="Analysis complete",
            blocks=blocks,
        )

        assert result == True
        assert mock_client.chat_postMessage.called
