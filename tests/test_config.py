"""Tests for configuration loading."""

import pytest
import tempfile
from pathlib import Path

import yaml

from ai_alert.config import Config, load_config, SlackConfig, SentryConfig


def test_config_defaults():
    """Test default configuration values."""
    config = Config()

    assert config.slack.channel == "rnd_cyberpunks_alarms"
    assert config.sentry.organization == "arcticwolf"
    assert config.sentry.project == "cx-collector"
    assert config.claude.model == "claude-sonnet-5-5"
    assert config.logging.level == "info"


def test_config_yaml_loading():
    """Test loading config from YAML file."""
    yaml_content = {
        "slack": {"channel": "custom-channel"},
        "sentry": {"organization": "custom-org"},
        "claude": {"model": "claude-opus-5-5", "effort": "high"},
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(yaml_content, f)
        temp_path = f.name

    try:
        config = Config.from_yaml(temp_path)
        assert config.slack.channel == "custom-channel"
        assert config.sentry.organization == "custom-org"
        assert config.claude.model == "claude-opus-5-5"
        assert config.claude.effort == "high"
    finally:
        Path(temp_path).unlink()


def test_config_missing_yaml_uses_defaults():
    """Test that missing YAML file uses defaults."""
    config = Config.from_yaml("/nonexistent/config.yaml")
    assert config.slack.channel == "rnd_cyberpunks_alarms"


def test_config_redacted_output(config):
    """Test that sensitive values are redacted."""
    import os

    os.environ["SLACK_BOT_TOKEN"] = "xoxb-secret-token"
    os.environ["SENTRY_API_TOKEN"] = "sntrys-secret-token"

    redacted = config.to_dict_redacted()

    assert redacted.get("SLACK_BOT_TOKEN") == "***REDACTED***"
    assert redacted.get("SENTRY_API_TOKEN") == "***REDACTED***"

    # Clean up
    del os.environ["SLACK_BOT_TOKEN"]
    del os.environ["SENTRY_API_TOKEN"]


def test_config_directory_paths(config):
    """Test that database and log directories are properly configured."""
    assert "data.db" in config.storage.db_path
    assert "logs" in config.logging.dir


def test_load_config_function():
    """Test load_config convenience function."""
    config = load_config()
    assert isinstance(config, Config)
    assert config.slack.channel == "rnd_cyberpunks_alarms"
