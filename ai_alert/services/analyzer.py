"""Main orchestrator combining Sentry fetcher, Claude client, and Store."""

from typing import Optional
from datetime import datetime
import os

from ai_alert.store import Store
from ai_alert.models import Alert, Analysis, AlertStatus
from ai_alert.config import Config
from ai_alert.logger import get_logger
from ai_alert.services.sentry_fetcher import SentryFetcher
from ai_alert.services.claude_client import ClaudeClient, build_system_prompt, build_user_prompt
from ai_alert.services.codebase_analyzer import CodebaseAnalyzer
from ai_alert.services.cloudwatch_fetcher import CloudWatchFetcher

logger = get_logger("analyzer")


class Analyzer:
    """Orchestrates alert analysis: fetch from Sentry, call Claude, persist to Store."""

    def __init__(
        self,
        config: Config,
        store: Store,
        sentry_fetcher: Optional[SentryFetcher] = None,
        claude_client: Optional[ClaudeClient] = None,
        codebase_analyzer: Optional[CodebaseAnalyzer] = None,
        cloudwatch_fetcher: Optional[CloudWatchFetcher] = None,
    ):
        """Initialize Analyzer.

        Args:
            config: Configuration
            store: SQLite store
            sentry_fetcher: Optional SentryFetcher (created if not provided)
            claude_client: Optional ClaudeClient (created if not provided)
            codebase_analyzer: Optional CodebaseAnalyzer (created if not provided)
            cloudwatch_fetcher: Optional CloudWatchFetcher (created if not provided)
        """
        self.config = config
        self.store = store

        # Initialize Sentry fetcher if not provided
        if sentry_fetcher is None:
            sentry_token = os.environ.get("SENTRY_API_TOKEN")
            if not sentry_token:
                raise ValueError("SENTRY_API_TOKEN environment variable not set")
            sentry_fetcher = SentryFetcher(
                organization=config.sentry.organization,
                api_token=sentry_token,
                sentry_host="arcticwolf.sentry.io",  # Use organization's Sentry instance
            )
        self.sentry_fetcher = sentry_fetcher

        # Initialize Claude client if not provided
        if claude_client is None:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable not set")
            claude_client = ClaudeClient(
                api_key=api_key,
                model=config.claude.model,
                max_tokens=config.claude.max_tokens,
            )
        self.claude_client = claude_client

        # Initialize CodebaseAnalyzer if not provided (optional for Phase 5+)
        if codebase_analyzer is None:
            codebase_repo = config.codebase.repo_path if hasattr(config.codebase, "repo_path") else None
            if codebase_repo:
                try:
                    codebase_analyzer = CodebaseAnalyzer(repo_path=codebase_repo)
                except ValueError as e:
                    logger.warning(f"Could not initialize CodebaseAnalyzer: {e}")
                    codebase_analyzer = None
            else:
                logger.debug("No codebase.repo_path configured, skipping CodebaseAnalyzer")
        self.codebase_analyzer = codebase_analyzer

        # Initialize CloudWatchFetcher if not provided (optional for Phase 6+)
        if cloudwatch_fetcher is None:
            if hasattr(config, "cloudwatch") and hasattr(config.cloudwatch, "enabled") and config.cloudwatch.enabled:
                try:
                    cloudwatch_fetcher = CloudWatchFetcher(
                        region=config.cloudwatch.region,
                        log_group_prefix=config.cloudwatch.log_group_prefix,
                        lookback_minutes=config.cloudwatch.lookback_minutes,
                    )
                except Exception as e:
                    logger.warning(f"Could not initialize CloudWatchFetcher: {e}")
                    cloudwatch_fetcher = None
            else:
                logger.debug("CloudWatch not enabled or not configured, skipping CloudWatchFetcher")
        self.cloudwatch_fetcher = cloudwatch_fetcher

        logger.info("Analyzer initialized")

    def analyze_alert(
        self,
        sentry_issue_id: str,
        force: bool = False,
        dry_run: bool = False,
    ) -> Optional[Analysis]:
        """Analyze a Sentry alert.

        Flow:
        1. Check if already analyzed (unless force=True)
        2. Fetch issue details from Sentry
        3. Fetch latest event from Sentry
        4. Build evidence bundle
        5. Call Claude with system + user prompts
        6. Persist Analysis to Store
        7. Return Analysis

        Args:
            sentry_issue_id: Sentry issue ID (numeric)
            force: Force re-analysis even if already done
            dry_run: Gather evidence and show prompt, don't call Claude

        Returns:
            Analysis object or None if fetch fails

        Raises:
            ValueError: On missing environment variables or API errors
        """
        logger.info(f"Starting analysis: sentry_issue_id={sentry_issue_id}, force={force}, dry_run={dry_run}")

        # Check for duplicate (dedup key)
        if not force:
            existing = self.store.get_alert_by_sentry_id(sentry_issue_id)
            if existing and existing.status == AlertStatus.ANALYZED:
                logger.info(f"Alert {sentry_issue_id} already analyzed, skipping")
                return self.store.get_analysis_by_alert_id(existing.id)

        # Create Alert record if not exists
        try:
            existing_alert = self.store.get_alert_by_sentry_id(sentry_issue_id)
            if existing_alert:
                alert = existing_alert
                alert.status = AlertStatus.ANALYZING
            else:
                # Fetch issue to get title and URL
                issue = self.sentry_fetcher.get_issue(sentry_issue_id)
                if not issue:
                    logger.error(f"Issue {sentry_issue_id} not found in Sentry")
                    return None

                alert = Alert(
                    sentry_issue_id=sentry_issue_id,
                    sentry_url=issue.get("url", f"https://sentry.io/organizations/{self.config.sentry.organization}/issues/{sentry_issue_id}/"),
                    title=issue.get("title", "Unknown error"),
                    slack_channel=self.config.slack.channel,
                    status=AlertStatus.ANALYZING,
                )
            self.store.save_alert(alert)
            logger.debug(f"Alert record created/updated: {alert.id}")
        except Exception as e:
            logger.error(f"Failed to create alert record: {e}")
            return None

        try:
            # Fetch latest event
            event = self.sentry_fetcher.get_latest_event(sentry_issue_id)
            if not event:
                logger.warning(f"No events found for issue {sentry_issue_id}")
                event = {}

            # Build evidence (Phase 5: code context, Phase 6: CloudWatch logs)
            code_context = self._gather_code_context(event) if self.codebase_analyzer else ""
            cloudwatch_logs = self._gather_cloudwatch_logs(event, sentry_issue_id) if self.cloudwatch_fetcher else ""

            # Build prompts
            system_prompt = build_system_prompt()
            user_prompt = build_user_prompt(
                sentry_event=event,
                code_context=code_context,
                cloudwatch_logs=cloudwatch_logs,
            )

            if dry_run:
                logger.info("Dry run mode: showing prompt, not calling Claude")
                return None

            # Call Claude
            logger.info("Calling Claude API for analysis")
            recommendation, tokens_used = self.claude_client.analyze(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )

            # Create Analysis record
            analysis = Analysis(
                alert_id=alert.id,
                sentry_issue_id=sentry_issue_id,
                model=self.claude_client.model,
                root_cause=recommendation.summary,
                confidence="high",  # Phase 4+: extract from Claude response
                error_category="unknown",  # Phase 4+: classify from stack trace
                affected_component="unknown",  # Phase 4+: extract from stack trace
                recommendation=recommendation,
                tokens_used=tokens_used,
            )

            # Persist to Store
            self.store.save_analysis(analysis)
            logger.info(f"Analysis saved: {analysis.id}")

            # Update alert status to analyzed
            self.store.update_alert_status(alert.id, AlertStatus.ANALYZED.value)
            logger.debug(f"Alert {alert.id} marked as ANALYZED")

            return analysis

        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            self.store.update_alert_status(
                alert.id,
                AlertStatus.FAILED.value,
                error_msg=str(e),
            )
            raise

    def _gather_code_context(self, sentry_event: dict) -> str:
        """Gather code context from stack trace frames.

        Args:
            sentry_event: Sentry event dict

        Returns:
            Formatted code context string (empty if no frames or codebase unavailable)
        """
        if not self.codebase_analyzer:
            return ""

        try:
            context_parts = []

            # Extract exception frames from Sentry event
            exceptions = sentry_event.get("exception", {}).get("values", [])
            if not exceptions:
                return ""

            for exc in exceptions:
                stacktrace = exc.get("stacktrace", {})
                frames = stacktrace.get("frames", [])

                # Focus on in_app frames (from the application, not libraries)
                in_app_frames = [f for f in frames if f.get("in_app", False)]
                if not in_app_frames:
                    in_app_frames = frames[:3]  # Fallback to first 3 frames

                for frame in in_app_frames[:3]:  # Limit to first 3 frames
                    filename = frame.get("filename", "")
                    lineno = frame.get("lineno", 0)

                    if not filename or not lineno:
                        continue

                    # Extract snippet
                    snippet = self.codebase_analyzer.extract_snippet(
                        file_path=filename,
                        line_num=lineno,
                        context_lines=10,
                    )

                    if snippet:
                        context_parts.append(f"### File: {filename}:{lineno}\n```\n{snippet}\n```")

            return "\n\n".join(context_parts)

        except Exception as e:
            logger.warning(f"Failed to gather code context: {e}")
            return ""

    def _gather_cloudwatch_logs(self, sentry_event: dict, sentry_issue_id: str) -> str:
        """Gather CloudWatch logs for pod around error time (best-effort).

        Args:
            sentry_event: Sentry event dict
            sentry_issue_id: Issue ID for logging

        Returns:
            Raw log lines as string (empty if unavailable)
        """
        if not self.cloudwatch_fetcher:
            return ""

        try:
            # Extract pod ID from Sentry tags
            tags = sentry_event.get("tags", {})
            pod_id = self.cloudwatch_fetcher.extract_pod_from_tags(tags)

            if not pod_id:
                logger.debug(f"No pod ID found in Sentry event for issue {sentry_issue_id}")
                return ""

            # Extract event timestamp
            timestamp_str = sentry_event.get("timestamp")
            try:
                if timestamp_str:
                    # Sentry timestamps are ISO format strings
                    error_timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                else:
                    error_timestamp = datetime.utcnow()
            except (ValueError, AttributeError):
                error_timestamp = datetime.utcnow()

            logger.debug(f"Querying CloudWatch logs for pod={pod_id}, issue={sentry_issue_id}")

            # Query CloudWatch logs
            logs = self.cloudwatch_fetcher.query_pod_logs(
                pod_id=pod_id,
                error_timestamp=error_timestamp,
                limit=100,
            )

            if logs:
                logger.info(f"Retrieved CloudWatch logs for pod {pod_id}")
                return logs

            return ""

        except Exception as e:
            logger.warning(f"Failed to gather CloudWatch logs: {e}")
            return ""

    def list_pending_alerts(self, limit: int = 10) -> list:
        """List pending alerts (not yet analyzed).

        Args:
            limit: Maximum number to return

        Returns:
            List of Alert objects
        """
        return self.store.list_alerts(status=AlertStatus.PENDING.value, limit=limit)

    def get_statistics(self) -> dict:
        """Get statistics on alerts and analyses.

        Returns:
            Dict with counts by status
        """
        return self.store.get_stats()

    def close(self):
        """Close all resources."""
        self.sentry_fetcher.close()
        if self.codebase_analyzer:
            self.codebase_analyzer.close()
        if self.cloudwatch_fetcher:
            self.cloudwatch_fetcher.close()
        self.store.close()
        logger.info("Analyzer closed")
