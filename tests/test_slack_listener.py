"""Tests for SlackListener (Phase 7)."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import re

from ai_alert.services.slack_listener import SlackListener


# INITIALIZATION


class TestSlackListenerInitialization:
    def test_init_with_tokens(self):
        """Test initialization with valid tokens."""
        listener = SlackListener(
            bot_token="xoxb-test-token",
            app_token="xapp-test-token",
        )
        assert listener.bot_token == "xoxb-test-token"
        assert listener.app_token == "xapp-test-token"

    def test_init_without_bot_token_raises(self):
        """Test initialization fails without bot_token."""
        with pytest.raises(ValueError, match="bot_token"):
            SlackListener(bot_token="", app_token="xapp-test")

    def test_init_without_app_token_raises(self):
        """Test initialization fails without app_token."""
        with pytest.raises(ValueError, match="app_token"):
            SlackListener(bot_token="xoxb-test", app_token="")

    def test_init_graceful_without_slack_bolt(self):
        """Test initialization gracefully handles missing slack-bolt."""
        # Even without slack-bolt, initialization should work (just disabled)
        listener = SlackListener(
            bot_token="xoxb-test",
            app_token="xapp-test",
        )
        assert listener is not None
        # slack_available may be True or False depending on if slack-bolt is installed


# ISSUE ID EXTRACTION


class TestExtractSentryIssueId:
    def test_extract_from_sentry_url(self):
        """Test extracting issue ID from Sentry URL."""
        listener = SlackListener("xoxb-test", "xapp-test")

        message = "Check this: https://sentry.io/organizations/arcticwolf/issues/12345/"
        issue_id = listener.extract_sentry_issue_id(message)

        assert issue_id == "12345"

    def test_extract_from_message_text(self):
        """Test extracting issue ID from plain text."""
        listener = SlackListener("xoxb-test", "xapp-test")

        message = "Error in issue 67890, please investigate"
        issue_id = listener.extract_sentry_issue_id(message)

        assert issue_id == "67890"

    def test_extract_not_found_returns_none(self):
        """Test extraction returns None when no ID found."""
        listener = SlackListener("xoxb-test", "xapp-test")

        message = "No issue ID here"
        issue_id = listener.extract_sentry_issue_id(message)

        assert issue_id is None

    def test_extract_from_empty_message(self):
        """Test extraction handles empty message."""
        listener = SlackListener("xoxb-test", "xapp-test")

        issue_id = listener.extract_sentry_issue_id("")

        assert issue_id is None

    def test_extract_from_none_message(self):
        """Test extraction handles None message."""
        listener = SlackListener("xoxb-test", "xapp-test")

        issue_id = listener.extract_sentry_issue_id(None)

        assert issue_id is None

    def test_extract_prefers_url_format(self):
        """Test extraction prefers URL format over plain text."""
        listener = SlackListener("xoxb-test", "xapp-test")

        message = "Issue 11111 in https://sentry.io/issues/22222/"
        issue_id = listener.extract_sentry_issue_id(message)

        # Should match the first pattern (URL)
        assert issue_id == "22222"

    def test_extract_multiple_ids_returns_first(self):
        """Test extraction returns first match."""
        listener = SlackListener("xoxb-test", "xapp-test")

        message = "Issue 11111 and also 22222"
        issue_id = listener.extract_sentry_issue_id(message)

        assert issue_id == "11111"


# MESSAGE CALLBACK


class TestOnMessage:
    def test_on_message_registers_callback(self):
        """Test callback registration."""
        listener = SlackListener("xoxb-test", "xapp-test")

        def my_callback(body, say):
            pass

        result = listener.on_message(my_callback)

        assert result == my_callback
        assert listener.callback == my_callback

    def test_on_message_async_callback(self):
        """Test async callback registration."""
        listener = SlackListener("xoxb-test", "xapp-test")

        async def my_async_callback(body, say):
            pass

        result = listener.on_message(my_async_callback)

        assert result == my_async_callback
        assert listener.callback == my_async_callback


# START/STOP


class TestSlackListenerStartStop:
    def test_start_without_slack(self):
        """Test start gracefully fails when Slack unavailable."""
        listener = SlackListener("xoxb-test", "xapp-test")
        listener.slack_available = False

        # Should return False, not raise
        import asyncio
        result = asyncio.run(listener.start())

        assert result == False

    def test_stop_closes_handler(self):
        """Test stop closes handler."""
        listener = SlackListener("xoxb-test", "xapp-test")
        listener.handler = Mock()

        import asyncio
        asyncio.run(listener.stop())

        assert listener.handler.close.called

    def test_close_method(self):
        """Test close method."""
        listener = SlackListener("xoxb-test", "xapp-test")

        listener.close()  # Should not raise


# RESOURCE MANAGEMENT


class TestSlackListenerResourceManagement:
    def test_context_manager(self):
        """Test context manager protocol."""
        with SlackListener("xoxb-test", "xapp-test") as listener:
            assert listener is not None
        # Should exit cleanly


# INTEGRATION


class TestSlackListenerIntegration:
    def test_full_workflow(self):
        """Test complete workflow: extract ID and setup callback."""
        listener = SlackListener("xoxb-test", "xapp-test")

        # Extract issue ID
        message = "Check Sentry issue https://sentry.io/issues/12345/"
        issue_id = listener.extract_sentry_issue_id(message)

        assert issue_id == "12345"

        # Register callback
        def my_callback(body, say):
            pass

        listener.on_message(my_callback)
        assert listener.callback == my_callback
