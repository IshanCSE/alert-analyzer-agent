"""Configuration management for AI Alert Agent."""

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class SlackConfig(BaseModel):
    """Slack configuration."""
    channel: str = "rnd_cyberpunks_alarms"


class SentryConfig(BaseModel):
    """Sentry configuration."""
    organization: str = "arcticwolf"
    project: str = "cx-collector"


class CloudWatchConfig(BaseModel):
    """CloudWatch configuration."""
    enabled: bool = True
    log_group_prefix: str = "/eks/cx-collector"
    region: str = "us-west-2"
    lookback_minutes: int = 5


class CodebaseConfig(BaseModel):
    """Codebase analysis configuration."""
    repo_path: str = str(Path.home() / "projects" / "cx-collector")


class ClaudeConfig(BaseModel):
    """Claude API configuration."""
    model: str = "claude-sonnet-5-5"
    effort: str = "medium"
    max_tokens: int = 8000


class DaemonConfig(BaseModel):
    """Daemon configuration."""
    slack_post_reply: bool = True


class StorageConfig(BaseModel):
    """Storage configuration."""
    db_path: str = str(Path.home() / ".ai-alert" / "data.db")


class LoggingConfig(BaseModel):
    """Logging configuration."""
    dir: str = str(Path.home() / ".ai-alert" / "logs")
    level: str = "info"


class Config(BaseSettings):
    """Main configuration for AI Alert Agent."""
    slack: SlackConfig = Field(default_factory=SlackConfig)
    sentry: SentryConfig = Field(default_factory=SentryConfig)
    cloudwatch: CloudWatchConfig = Field(default_factory=CloudWatchConfig)
    codebase: CodebaseConfig = Field(default_factory=CodebaseConfig)
    claude: ClaudeConfig = Field(default_factory=ClaudeConfig)
    daemon: DaemonConfig = Field(default_factory=DaemonConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    class Config:
        env_file = str(Path.home() / ".ai-alert" / ".env")
        env_file_encoding = "utf-8"
        case_sensitive = False
        nested_delimiter = "__"

    @classmethod
    def from_yaml(cls, path: Optional[str] = None) -> "Config":
        """Load configuration from YAML file."""
        if path is None:
            path = str(Path.home() / ".ai-alert" / "config.yaml")

        config_data = {}
        if Path(path).exists():
            with open(path) as f:
                config_data = yaml.safe_load(f) or {}

        # Convert YAML keys from snake_case to our model names
        if "slack" in config_data:
            config_data["slack"] = SlackConfig(**config_data["slack"])
        if "sentry" in config_data:
            config_data["sentry"] = SentryConfig(**config_data["sentry"])
        if "cloudwatch" in config_data:
            config_data["cloudwatch"] = CloudWatchConfig(**config_data["cloudwatch"])
        if "codebase" in config_data:
            config_data["codebase"] = CodebaseConfig(**config_data["codebase"])
        if "claude" in config_data:
            config_data["claude"] = ClaudeConfig(**config_data["claude"])
        if "daemon" in config_data:
            config_data["daemon"] = DaemonConfig(**config_data["daemon"])
        if "storage" in config_data:
            config_data["storage"] = StorageConfig(**config_data["storage"])
        if "logging" in config_data:
            config_data["logging"] = LoggingConfig(**config_data["logging"])

        # Merge with environment variables
        return cls(**config_data)

    def to_dict_redacted(self) -> dict:
        """Return config as dict with secrets redacted."""
        config_dict = self.model_dump()

        # Redact sensitive environment variables
        secrets = [
            "SLACK_BOT_TOKEN",
            "SLACK_APP_TOKEN",
            "SENTRY_API_TOKEN",
            "ANTHROPIC_API_KEY",
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
        ]

        for secret in secrets:
            if secret in os.environ:
                config_dict[secret] = "***REDACTED***"

        return config_dict


def load_config(config_path: Optional[str] = None) -> Config:
    """Load configuration from YAML and environment variables."""
    return Config.from_yaml(config_path)
