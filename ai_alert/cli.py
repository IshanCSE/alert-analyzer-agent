"""CLI commands for AI Alert Agent."""

import click
import json
from pathlib import Path
import os
import asyncio
import signal

from ai_alert import __version__
from ai_alert.config import load_config
from ai_alert.logger import setup_logger, get_logger
from ai_alert.store import Store
from ai_alert.services.sentry_fetcher import SentryFetcher
from ai_alert.services.analyzer import Analyzer
from ai_alert.services.slack_listener import SlackListener
from ai_alert.services.slack_poster import SlackPoster


@click.group()
@click.version_option(version=__version__)
def main():
    """AI Alert Agent - Sentry alert triage with Claude analysis."""
    pass


@main.command()
@click.option(
    "--config",
    type=click.Path(exists=False),
    default=str(Path.home() / ".ai-alert" / "config.yaml"),
    help="Path to config file",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default="INFO",
    help="Logging level",
)
def config_check(config: str, log_level: str):
    """Validate and display configuration."""
    setup_logger(level=log_level)
    logger = get_logger("config_check")

    try:
        cfg = load_config(config)
        logger.info("✓ Configuration loaded successfully")

        # Display config (redacted)
        config_dict = cfg.to_dict_redacted()
        click.echo("\nResolved Configuration:")
        click.echo(json.dumps(config_dict, indent=2, default=str))

        # Verify required directories exist or can be created
        db_path = Path(cfg.storage.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"✓ Database directory ready: {db_path.parent}")

        log_dir = Path(cfg.logging.dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"✓ Logs directory ready: {log_dir}")

        click.echo("\n✓ All checks passed!")

    except Exception as e:
        logger.error(f"✗ Configuration check failed: {e}")
        click.echo(f"\n✗ Error: {e}", err=True)
        raise SystemExit(1)


@main.command()
def version():
    """Display version information."""
    click.echo(f"ai-alert {__version__}")


@main.command()
@click.argument("sentry_issue_id")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Gather evidence and show prompt (no Claude call)",
)
@click.option(
    "--force",
    is_flag=True,
    help="Re-analyze even if already analyzed",
)
@click.option(
    "--config",
    type=click.Path(exists=False),
    default=str(Path.home() / ".ai-alert" / "config.yaml"),
    help="Path to config file",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default="INFO",
    help="Logging level",
)
def analyze(sentry_issue_id: str, dry_run: bool, force: bool, config: str, log_level: str):
    """Analyze a specific Sentry issue."""
    setup_logger(level=log_level)
    logger = get_logger("analyze")

    try:
        cfg = load_config(config)
        logger.info(f"Analyzing Sentry issue: {sentry_issue_id}")
        logger.info(f"Dry run: {dry_run}, Force: {force}")

        click.echo(f"\n📊 Analyzing Sentry issue {sentry_issue_id}...")

        # Initialize Store and Analyzer
        store = Store(db_path=str(cfg.storage.db_path))
        analyzer = Analyzer(config=cfg, store=store)

        try:
            click.echo("🔍 Fetching issue details from Sentry...")

            if dry_run:
                result = analyzer.analyze_alert(
                    sentry_issue_id=sentry_issue_id,
                    force=force,
                    dry_run=True,
                )
                click.echo("\n[DRY RUN] Evidence gathered. System prompt and user prompt would be sent to Claude.\n")
                click.echo("Would call Claude API (skipped in dry-run mode)")
            else:
                result = analyzer.analyze_alert(
                    sentry_issue_id=sentry_issue_id,
                    force=force,
                    dry_run=False,
                )

                if result:
                    click.echo("\n✅ Analysis complete!\n")
                    click.echo("Root Cause Analysis:")
                    click.echo("=" * 80)
                    click.echo(f"Summary: {result.recommendation.summary}\n")
                    click.echo(f"Confidence: {result.confidence}")
                    click.echo(f"Error Category: {result.error_category}")
                    click.echo(f"Affected Component: {result.affected_component}\n")

                    click.echo("Suggested Fix:")
                    click.echo(f"{result.recommendation.suggested_fix}\n")

                    if result.recommendation.files_to_inspect:
                        click.echo("Files to Inspect:")
                        for f in result.recommendation.files_to_inspect:
                            click.echo(f"  • {f}")
                        click.echo()

                    if result.recommendation.follow_up_actions:
                        click.echo("Follow-up Actions:")
                        for action in result.recommendation.follow_up_actions:
                            click.echo(f"  • {action}")
                        click.echo()

                    click.echo(f"Tokens Used: {result.tokens_used}")
                    click.echo(f"Model: {result.model}")
                else:
                    click.echo(f"✗ Analysis failed or issue not found")
                    raise SystemExit(1)

        finally:
            analyzer.close()

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        click.echo(f"\n✗ Error: {e}", err=True)
        raise SystemExit(1)
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        click.echo(f"\n✗ Error: {e}", err=True)
        raise SystemExit(1)


@main.command()
@click.option(
    "--config",
    type=click.Path(exists=False),
    default=str(Path.home() / ".ai-alert" / "config.yaml"),
    help="Path to config file",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default="INFO",
    help="Logging level",
)
def status(config: str, log_level: str):
    """Check daemon status and database statistics."""
    setup_logger(level=log_level)
    logger = get_logger("status")

    try:
        cfg = load_config(config)
        logger.info("Checking status...")

        db_path = Path(cfg.storage.db_path)
        if db_path.exists():
            db_size = db_path.stat().st_size / 1024  # KB
            click.echo(f"✓ Database: {db_path} ({db_size:.2f} KB)")
        else:
            click.echo(f"⊘ Database: Not initialized yet")

        click.echo(f"✓ Config: {Path(config).name}")
        click.echo(f"✓ Logs: {cfg.logging.dir}")

        with Store(db_path=str(cfg.storage.db_path)) as store:
            stats = store.get_stats()
            click.echo("\nAlert counts:")
            click.echo(f"  Total:     {stats['total_alerts']}")
            click.echo(f"  Pending:   {stats['pending']}")
            click.echo(f"  Analyzing: {stats['analyzing']}")
            click.echo(f"  Analyzed:  {stats['analyzed']}")
            click.echo(f"  Failed:    {stats['failed']}")
            click.echo(f"\nTotal analyses: {stats['total_analyses']}")

    except Exception as e:
        logger.error(f"Status check failed: {e}")
        click.echo(f"\n✗ Error: {e}", err=True)
        raise SystemExit(1)


@main.command()
@click.option(
    "--status",
    type=click.Choice(["pending", "analyzing", "analyzed", "failed", "all"]),
    default="all",
    help="Filter by alert status",
)
@click.option(
    "--limit",
    type=int,
    default=50,
    help="Maximum number of alerts to display",
)
@click.option(
    "--config",
    type=click.Path(exists=False),
    default=str(Path.home() / ".ai-alert" / "config.yaml"),
    help="Path to config file",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default="INFO",
    help="Logging level",
)
def list(status: str, limit: int, config: str, log_level: str):
    """List alerts from the database."""
    setup_logger(level=log_level)
    logger = get_logger("list")

    try:
        cfg = load_config(config)

        with Store(db_path=str(cfg.storage.db_path)) as store:
            if status == "all":
                alerts = store.list_alerts(limit=limit)
            else:
                alerts = store.list_alerts(status=status, limit=limit)

            if not alerts:
                click.echo("No alerts found.")
                return

            click.echo(f"\n📋 {len(alerts)} Alert(s):\n")
            for alert in alerts:
                status_emoji = {
                    "pending": "⏳",
                    "analyzing": "🔍",
                    "analyzed": "✅",
                    "failed": "❌",
                }.get(alert.status, "❓")

                click.echo(f"{status_emoji} {alert.id[:8]}... | {alert.sentry_issue_id}")
                click.echo(f"   Title: {alert.title}")
                click.echo(f"   Status: {alert.status} | Received: {alert.received_at.strftime('%Y-%m-%d %H:%M:%S')}")
                if alert.last_error:
                    click.echo(f"   Error: {alert.last_error}")
                click.echo()

    except Exception as e:
        logger.error(f"List failed: {e}")
        click.echo(f"\n✗ Error: {e}", err=True)
        raise SystemExit(1)


@main.command()
@click.argument("alert_id")
@click.option(
    "--config",
    type=click.Path(exists=False),
    default=str(Path.home() / ".ai-alert" / "config.yaml"),
    help="Path to config file",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default="INFO",
    help="Logging level",
)
def show(alert_id: str, config: str, log_level: str):
    """Show full details of an alert and its analysis."""
    setup_logger(level=log_level)
    logger = get_logger("show")

    try:
        cfg = load_config(config)

        with Store(db_path=str(cfg.storage.db_path)) as store:
            alert = store.get_alert_by_id(alert_id)
            if not alert:
                click.echo(f"✗ Alert {alert_id} not found")
                raise SystemExit(1)

            click.echo(f"\n📌 Alert: {alert.id}\n")
            click.echo(f"Sentry Issue ID: {alert.sentry_issue_id}")
            click.echo(f"Title: {alert.title}")
            click.echo(f"Status: {alert.status}")
            click.echo(f"Slack Channel: {alert.slack_channel}")
            click.echo(f"Received: {alert.received_at.strftime('%Y-%m-%d %H:%M:%S')}")
            click.echo(f"URL: {alert.sentry_url}")

            if alert.last_error:
                click.echo(f"\n⚠️  Last Error: {alert.last_error}")

            # Show analysis if available
            analysis = store.get_analysis_by_alert_id(alert.id)
            if analysis:
                click.echo(f"\n📊 Analysis:\n")
                click.echo(f"Model: {analysis.model}")
                click.echo(f"Root Cause: {analysis.root_cause}")
                click.echo(f"Confidence: {analysis.confidence}")
                click.echo(f"Error Category: {analysis.error_category}")
                click.echo(f"Affected Component: {analysis.affected_component}")
                click.echo(f"Tokens Used: {analysis.tokens_used}")
                click.echo(f"Created: {analysis.created_at.strftime('%Y-%m-%d %H:%M:%S')}")

                click.echo(f"\n💡 Recommendation:\n")
                rec = analysis.recommendation
                click.echo(f"Summary: {rec.summary}")
                click.echo(f"Suggested Fix: {rec.suggested_fix}")
                if rec.files_to_inspect:
                    click.echo(f"Files to Inspect:")
                    for f in rec.files_to_inspect:
                        click.echo(f"  • {f}")
                if rec.follow_up_actions:
                    click.echo(f"Follow-up Actions:")
                    for a in rec.follow_up_actions:
                        click.echo(f"  • {a}")
            else:
                click.echo("\n⏳ No analysis yet (status: pending or analyzing)")

    except Exception as e:
        logger.error(f"Show failed: {e}")
        click.echo(f"\n✗ Error: {e}", err=True)
        raise SystemExit(1)


@main.command()
@click.option(
    "--days",
    type=int,
    default=30,
    help="Delete alerts older than this many days",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be deleted without deleting",
)
@click.option(
    "--config",
    type=click.Path(exists=False),
    default=str(Path.home() / ".ai-alert" / "config.yaml"),
    help="Path to config file",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default="INFO",
    help="Logging level",
)
def gc(days: int, dry_run: bool, config: str, log_level: str):
    """Garbage collect old alerts."""
    setup_logger(level=log_level)
    logger = get_logger("gc")

    try:
        cfg = load_config(config)
        from datetime import datetime, timedelta

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        with Store(db_path=str(cfg.storage.db_path)) as store:
            # Get all alerts older than cutoff
            all_alerts = store.list_alerts(limit=10000)  # Get all
            old_alerts = [a for a in all_alerts if a.received_at < cutoff_date]

            if not old_alerts:
                click.echo(f"No alerts older than {days} days found.")
                return

            click.echo(f"\n🗑️  Found {len(old_alerts)} alert(s) older than {days} days\n")

            if dry_run:
                click.echo("[DRY RUN] Would delete:")
                for alert in old_alerts[:10]:  # Show first 10
                    click.echo(f"  • {alert.id[:8]}... | {alert.sentry_issue_id} | {alert.received_at.strftime('%Y-%m-%d')}")
                if len(old_alerts) > 10:
                    click.echo(f"  ... and {len(old_alerts) - 10} more")
                click.echo(f"\nRun without --dry-run to actually delete.")
            else:
                deleted_count = 0
                for alert in old_alerts:
                    try:
                        store.delete_alert(alert.id)
                        deleted_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to delete alert {alert.id}: {e}")

                click.echo(f"✅ Deleted {deleted_count} alert(s)")

    except Exception as e:
        logger.error(f"GC failed: {e}")
        click.echo(f"\n✗ Error: {e}", err=True)
        raise SystemExit(1)


@main.group()
def daemon():
    """Daemon commands (start, stop)."""
    pass


@daemon.command()
@click.option(
    "--foreground",
    is_flag=True,
    help="Run in foreground (log to stdout)",
)
@click.option(
    "--config",
    type=click.Path(exists=False),
    default=str(Path.home() / ".ai-alert" / "config.yaml"),
    help="Path to config file",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default="INFO",
    help="Logging level",
)
def start(foreground: bool, config: str, log_level: str):
    """Start the daemon."""
    setup_logger(level=log_level)
    logger = get_logger("daemon.start")

    async def run_daemon():
        """Run the daemon event loop."""
        try:
            cfg = load_config(config)
            logger.info("Starting AI Alert daemon...")
            logger.info(f"Foreground: {foreground}")
            logger.info(f"Channel: {cfg.slack.channel}")

            click.echo("\n🚀 AI Alert daemon starting...")
            click.echo(f"Listening to: #{cfg.slack.channel}")

            # Get Slack tokens from environment
            slack_bot_token = os.environ.get("SLACK_BOT_TOKEN")
            slack_app_token = os.environ.get("SLACK_APP_TOKEN")

            if not slack_bot_token or not slack_app_token:
                raise ValueError("SLACK_BOT_TOKEN and SLACK_APP_TOKEN environment variables required")

            # Initialize services
            store = Store(db_path=str(cfg.storage.db_path))
            analyzer = Analyzer(config=cfg, store=store)
            listener = SlackListener(bot_token=slack_bot_token, app_token=slack_app_token)
            poster = SlackPoster(bot_token=slack_bot_token)

            # Register message handler
            @listener.on_message
            async def handle_message(body, say):
                """Handle incoming Slack messages."""
                try:
                    # Extract issue ID from message
                    message_text = body.get("event", {}).get("text", "")
                    issue_id = listener.extract_sentry_issue_id(message_text)

                    if not issue_id:
                        logger.debug("No Sentry issue ID found in message")
                        return

                    logger.info(f"Found Sentry issue ID: {issue_id}")

                    # Analyze the alert
                    channel = body.get("event", {}).get("channel")
                    thread_ts = body.get("event", {}).get("thread_ts") or body.get("event", {}).get("ts")

                    analysis = analyzer.analyze_alert(sentry_issue_id=issue_id)

                    if analysis:
                        # Format and post reply
                        blocks = poster.format_analysis_blocks(analysis)
                        poster.post_reply(
                            channel=channel,
                            thread_ts=thread_ts,
                            text=f"✅ Analysis complete: {analysis.recommendation.summary}",
                            blocks=blocks,
                        )
                        logger.info(f"Posted analysis for issue {issue_id}")
                    else:
                        poster.post_reply(
                            channel=channel,
                            thread_ts=thread_ts,
                            text="⚠️ Analysis failed: could not fetch issue details",
                        )
                        logger.warning(f"Analysis failed for issue {issue_id}")

                except Exception as e:
                    logger.error(f"Error handling message: {e}")

            # Start listener
            success = await listener.start()
            if not success:
                raise RuntimeError("Failed to start Slack Socket Mode listener")

            click.echo("\n✅ Daemon running. Press Ctrl-C to stop.\n")

            # Keep running until interrupted
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                click.echo("\n\n⏹  Stopping daemon...")
                await listener.stop()
                analyzer.close()

        except Exception as e:
            logger.error(f"Daemon error: {e}")
            click.echo(f"\n✗ Error: {e}", err=True)
            raise SystemExit(1)

    # Run the async event loop
    if foreground:
        click.echo("\n(Press Ctrl-C to stop)\n")
        asyncio.run(run_daemon())
    else:
        # TODO: Implement background daemon mode with launchd/systemd
        click.echo("Background daemon mode not yet implemented (use --foreground for now)")
        raise SystemExit(1)


@daemon.command()
def stop():
    """Stop the daemon."""
    logger = get_logger("daemon.stop")
    logger.info("Stopping AI Alert daemon...")
    click.echo("⏹  Stopping daemon via Ctrl-C on foreground process")


if __name__ == "__main__":
    main()
