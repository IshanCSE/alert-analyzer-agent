"""Slack listener for Socket Mode (Phase 7)."""

import re
import json
from typing import Optional, Callable
import asyncio

from ai_alert.logger import get_logger

logger = get_logger("slack_listener")


class SlackListener:
    """Listens to Slack Socket Mode for incoming messages and alerts."""

    def __init__(self, bot_token: str, app_token: str):
        """
        Initialize SlackListener with Slack tokens.

        Args:
            bot_token: Slack bot token (xoxb-...)
            app_token: Slack app token for Socket Mode (xapp-...)

        Raises:
            ValueError: If tokens are missing or invalid
        """
        if not bot_token:
            raise ValueError("bot_token is required")
        if not app_token:
            raise ValueError("app_token is required")

        self.bot_token = bot_token
        self.app_token = app_token

        # Try to import slack_bolt
        try:
            from slack_bolt import App
            from slack_bolt.adapter.socket_mode import SocketModeHandler

            self.App = App
            self.SocketModeHandler = SocketModeHandler
            self.slack_available = True
            logger.info("Slack Bolt SDK available, Socket Mode enabled")
        except ImportError:
            logger.warning("slack-bolt not installed, Slack integration disabled")
            self.slack_available = False
            self.App = None
            self.SocketModeHandler = None

        self.app = None
        self.handler = None
        self.callback = None

        if self.slack_available:
            try:
                self.app = self.App(token=bot_token)
                logger.info("Slack app initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Slack app: {e}")
                self.slack_available = False

    def on_message(self, callback: Callable) -> Callable:
        """
        Register a callback for incoming messages.

        Args:
            callback: Async function(body, say) that handles messages

        Returns:
            The callback (for decorator use)
        """
        self.callback = callback

        if self.slack_available and self.app:
            # Register message handler with Slack Bolt
            @self.app.message(re.compile(".*"))  # Match all messages
            def handle_message(body, say, client):
                """Dispatch to callback."""
                try:
                    # Run callback in event loop if needed
                    if asyncio.iscoroutinefunction(callback):
                        asyncio.create_task(callback(body, say))
                    else:
                        callback(body, say)
                except Exception as e:
                    logger.error(f"Error handling message: {e}")

        return callback

    def extract_sentry_issue_id(self, message_text: str) -> Optional[str]:
        """
        Extract Sentry issue ID from message text.

        Args:
            message_text: Slack message text

        Returns:
            Issue ID (numeric string) or None if not found
        """
        if not message_text:
            return None

        # Look for Sentry URL patterns
        # https://sentry.io/organizations/arcticwolf/issues/12345/
        match = re.search(r"issues[/](\d+)", message_text)
        if match:
            logger.debug(f"Found Sentry issue ID in URL: {match.group(1)}")
            return match.group(1)

        # Look for bare issue ID (just numbers)
        match = re.search(r"\b(\d{5,})\b", message_text)
        if match:
            logger.debug(f"Found potential Sentry issue ID in text: {match.group(1)}")
            return match.group(1)

        logger.debug("No Sentry issue ID found in message")
        return None

    async def start(self) -> bool:
        """
        Start listening to Slack Socket Mode.

        Returns:
            True if started successfully, False otherwise
        """
        if not self.slack_available or not self.app:
            logger.warning("Slack not available, cannot start listener")
            return False

        try:
            self.handler = self.SocketModeHandler(self.app, self.app_token)
            logger.info("Starting Slack Socket Mode listener...")

            # Start handler in background
            self.handler.start()
            logger.info("Slack Socket Mode listener started")
            return True

        except Exception as e:
            logger.error(f"Failed to start Socket Mode listener: {e}")
            return False

    async def stop(self):
        """Stop listening to Slack Socket Mode."""
        if self.handler:
            try:
                self.handler.close()
                logger.info("Slack Socket Mode listener stopped")
            except Exception as e:
                logger.error(f"Error stopping Socket Mode listener: {e}")

    def close(self):
        """Close Slack listener."""
        asyncio.run(self.stop())
        logger.debug("SlackListener closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
