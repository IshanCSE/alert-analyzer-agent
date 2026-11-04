"""Slack poster for sending threaded replies (Phase 7)."""

from typing import Optional

from ai_alert.logger import get_logger

logger = get_logger("slack_poster")


class SlackPoster:
    """Posts analysis results back to Slack as threaded replies."""

    def __init__(self, bot_token: str):
        """
        Initialize SlackPoster with Slack bot token.

        Args:
            bot_token: Slack bot token (xoxb-...)

        Raises:
            ValueError: If bot_token is missing
        """
        if not bot_token:
            raise ValueError("bot_token is required")

        self.bot_token = bot_token

        # Try to import slack_sdk
        try:
            from slack_sdk import WebClient

            self.WebClient = WebClient
            self.client = WebClient(token=bot_token)
            self.slack_available = True
            logger.info("Slack SDK available")
        except ImportError:
            logger.warning("slack-sdk not installed, Slack posting disabled")
            self.slack_available = False
            self.WebClient = None
            self.client = None
        except Exception as e:
            logger.error(f"Failed to initialize Slack client: {e}")
            self.slack_available = False
            self.client = None

    def post_reply(
        self,
        channel: str,
        thread_ts: str,
        text: str,
        blocks: Optional[list] = None,
    ) -> bool:
        """
        Post a threaded reply to Slack.

        Args:
            channel: Channel ID (e.g., "C123ABC")
            thread_ts: Thread timestamp of parent message
            text: Plain text message
            blocks: Optional Slack Block Kit blocks for formatting

        Returns:
            True if posted successfully, False otherwise
        """
        if not self.slack_available or not self.client:
            logger.warning("Slack client not available, cannot post reply")
            return False

        if not channel or not thread_ts:
            logger.warning("channel and thread_ts are required")
            return False

        try:
            logger.debug(f"Posting reply to channel={channel}, thread_ts={thread_ts}")

            response = self.client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=text,
                blocks=blocks,
            )

            logger.info(f"Posted reply: ts={response['ts']}")
            return True

        except Exception as e:
            logger.error(f"Failed to post reply: {e}")
            return False

    def format_analysis_blocks(self, analysis) -> list:
        """
        Format Analysis object as Slack Block Kit blocks.

        Args:
            analysis: Analysis object with recommendation

        Returns:
            List of Block Kit blocks for rendering
        """
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Root Cause Analysis*\n{analysis.root_cause}",
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Confidence:* {analysis.confidence} | *Category:* {analysis.error_category} | *Component:* {analysis.affected_component}",
                    }
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Suggested Fix*\n{analysis.recommendation.suggested_fix}",
                },
            },
        ]

        # Add files to inspect if available
        if analysis.recommendation.files_to_inspect:
            files_text = "\n".join(
                [f"• {f}" for f in analysis.recommendation.files_to_inspect]
            )
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Files to Inspect*\n{files_text}",
                    },
                }
            )

        # Add follow-up actions if available
        if analysis.recommendation.follow_up_actions:
            actions_text = "\n".join(
                [f"• {a}" for a in analysis.recommendation.follow_up_actions]
            )
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Follow-up Actions*\n{actions_text}",
                    },
                }
            )

        # Add token info
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Tokens: {analysis.tokens_used} | Model: {analysis.model}",
                    }
                ],
            }
        )

        return blocks

    def close(self):
        """Close Slack poster."""
        self.client = None
        logger.debug("SlackPoster closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
