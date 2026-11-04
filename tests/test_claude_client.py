"""Tests for ClaudeClient and prompt building (Phase 4)."""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock

from ai_alert.services.claude_client import (
    ClaudeClient,
    build_system_prompt,
    build_user_prompt,
)
from ai_alert.models import Recommendation


@pytest.fixture
def claude_client():
    """Fixture: ClaudeClient instance for testing."""
    return ClaudeClient(
        api_key="sk-ant-test-key-12345",
        model="claude-sonnet-5-5",
        max_tokens=2048,
    )


# INITIALIZATION


class TestInitialization:
    def test_init_stores_config(self):
        client = ClaudeClient(
            api_key="sk-ant-test",
            model="claude-opus-5-5",
            max_tokens=4096,
        )
        assert client.model == "claude-opus-5-5"
        assert client.max_tokens == 4096
        assert client.api_key == "sk-ant-test"

    def test_init_defaults(self):
        client = ClaudeClient(api_key="sk-ant-test")
        assert client.model == "claude-sonnet-5-5"
        assert client.max_tokens == 2048

    def test_init_creates_anthropic_client(self):
        client = ClaudeClient(api_key="sk-ant-test")
        assert client.client is not None


# ANALYZE METHOD


class TestAnalyze:
    @patch("anthropic.Anthropic")
    def test_analyze_success(self, mock_anthropic_class, claude_client):
        """Test successful Claude API call."""
        # Mock the Anthropic client
        mock_client_instance = Mock()
        mock_anthropic_class.return_value = mock_client_instance

        # Create recommendation dict
        rec_dict = {
            "summary": "Null pointer in alerts collector",
            "suggested_fix": "Add null check before field access",
            "files_to_inspect": ["alerts.go", "alerts_test.go"],
            "related_code_paths": ["internal/collector/alerts/"],
            "follow_up_actions": ["review", "test"],
            "is_known_issue": False,
        }

        # Mock Claude response
        mock_response = Mock()
        mock_response.content = [Mock(text=json.dumps(rec_dict))]
        mock_response.usage.output_tokens = 150
        mock_response.usage.input_tokens = 800
        mock_client_instance.messages.create.return_value = mock_response

        # Create client with mocked anthropic
        client = ClaudeClient(api_key="sk-ant-test")
        client.client = mock_client_instance

        # Call analyze
        rec, tokens = client.analyze(
            system_prompt="You are an expert.",
            user_prompt="Analyze this error.",
        )

        assert isinstance(rec, Recommendation)
        assert rec.summary == "Null pointer in alerts collector"
        assert tokens == 950  # 150 + 800

    @patch("anthropic.Anthropic")
    def test_analyze_with_markdown_code_block(self, mock_anthropic_class, claude_client):
        """Test Claude response wrapped in markdown code block."""
        mock_client_instance = Mock()
        mock_anthropic_class.return_value = mock_anthropic_class

        rec_dict = {
            "summary": "Test",
            "suggested_fix": "Fix it",
            "files_to_inspect": ["test.go"],
            "related_code_paths": ["lib/"],
            "follow_up_actions": ["test"],
            "is_known_issue": False,
        }

        # Response with markdown wrapping
        json_response = f"```json\n{json.dumps(rec_dict)}\n```"

        mock_response = Mock()
        mock_response.content = [Mock(text=json_response)]
        mock_response.usage.output_tokens = 100
        mock_response.usage.input_tokens = 500
        mock_client_instance.messages.create.return_value = mock_response

        client = ClaudeClient(api_key="sk-ant-test")
        client.client = mock_client_instance

        rec, tokens = client.analyze(
            system_prompt="System",
            user_prompt="User",
        )

        assert isinstance(rec, Recommendation)
        assert rec.summary == "Test"

    @patch("anthropic.Anthropic")
    def test_analyze_invalid_json(self, mock_anthropic_class):
        """Test error handling for invalid JSON response."""
        mock_client_instance = Mock()
        mock_anthropic_class.return_value = mock_client_instance

        # Invalid JSON response
        mock_response = Mock()
        mock_response.content = [Mock(text="This is not JSON")]
        mock_response.usage.output_tokens = 100
        mock_response.usage.input_tokens = 500
        mock_client_instance.messages.create.return_value = mock_response

        client = ClaudeClient(api_key="sk-ant-test")
        client.client = mock_client_instance

        with pytest.raises(ValueError, match="not valid JSON"):
            client.analyze(system_prompt="S", user_prompt="U")

    @patch("anthropic.Anthropic")
    def test_analyze_missing_required_fields(self, mock_anthropic_class):
        """Test error when response is missing required fields."""
        mock_client_instance = Mock()
        mock_anthropic_class.return_value = mock_client_instance

        # JSON missing required fields
        bad_dict = {"summary": "test"}  # Missing other required fields

        mock_response = Mock()
        mock_response.content = [Mock(text=json.dumps(bad_dict))]
        mock_response.usage.output_tokens = 100
        mock_response.usage.input_tokens = 500
        mock_client_instance.messages.create.return_value = mock_response

        client = ClaudeClient(api_key="sk-ant-test")
        client.client = mock_client_instance

        with pytest.raises(ValueError):
            # Will fail Pydantic validation when creating Recommendation
            client.analyze(system_prompt="S", user_prompt="U")


# SYSTEM PROMPT


class TestSystemPrompt:
    def test_build_system_prompt(self):
        """Test system prompt generation."""
        prompt = build_system_prompt()

        # Should mention key concepts
        assert "cx-collector" in prompt
        assert "Collector" in prompt
        assert "error taxonomy" in prompt or "Error" in prompt
        assert "JSON" in prompt
        assert len(prompt) > 500  # Substantial prompt

    def test_system_prompt_includes_architecture(self):
        """Test system prompt covers architecture."""
        prompt = build_system_prompt()

        # Key patterns
        assert "Dependency Injection" in prompt or "Deps" in prompt
        assert "Registry" in prompt or "Component" in prompt

    def test_system_prompt_json_schema(self):
        """Test system prompt includes JSON schema."""
        prompt = build_system_prompt()

        # Should show expected output format
        assert "summary" in prompt
        assert "suggested_fix" in prompt
        assert "is_known_issue" in prompt


# USER PROMPT


class TestUserPrompt:
    def test_build_user_prompt_minimal(self):
        """Test user prompt with minimal Sentry event."""
        event = {"exception": {"values": []}}
        prompt = build_user_prompt(sentry_event=event)

        assert "Analyze this Sentry error" in prompt
        # Even minimal prompt has header, so check for at least header presence
        assert len(prompt) >= 28

    def test_build_user_prompt_with_exception(self):
        """Test user prompt includes exception details."""
        event = {
            "exception": {
                "values": [
                    {
                        "type": "NullPointerException",
                        "value": "null pointer at line 42",
                        "stacktrace": {
                            "frames": [
                                {
                                    "filename": "alerts.go",
                                    "lineno": 42,
                                    "function": "FetchAlerts",
                                }
                            ]
                        },
                    }
                ]
            }
        }
        prompt = build_user_prompt(sentry_event=event)

        assert "NullPointerException" in prompt
        assert "null pointer at line 42" in prompt
        assert "alerts.go" in prompt
        assert "Stack Trace" in prompt

    def test_build_user_prompt_with_tags(self):
        """Test user prompt includes context tags."""
        event = {
            "exception": {"values": []},
            "tags": {
                "pod": "cx-collector-pod-123",
                "release": "v1.2.3",
                "environment": "production",
            },
        }
        prompt = build_user_prompt(sentry_event=event)

        assert "Context Tags" in prompt
        assert "pod: cx-collector-pod-123" in prompt
        assert "release: v1.2.3" in prompt

    def test_build_user_prompt_with_breadcrumbs(self):
        """Test user prompt includes breadcrumbs."""
        event = {
            "exception": {"values": []},
            "breadcrumbs": [
                {
                    "timestamp": "2024-10-29T15:00:00Z",
                    "level": "info",
                    "message": "Starting alert fetch",
                },
                {
                    "timestamp": "2024-10-29T15:00:05Z",
                    "level": "error",
                    "message": "Null pointer exception",
                },
            ],
        }
        prompt = build_user_prompt(sentry_event=event)

        assert "Event Breadcrumbs" in prompt
        assert "Starting alert fetch" in prompt
        assert "Null pointer exception" in prompt

    def test_build_user_prompt_with_code_context(self):
        """Test user prompt includes code context."""
        event = {"exception": {"values": []}}
        code_context = "    value := obj[key]  // Null check missing\n"
        prompt = build_user_prompt(
            sentry_event=event,
            code_context=code_context,
        )

        assert "Relevant Code Context" in prompt
        assert "Null check missing" in prompt

    def test_build_user_prompt_with_logs(self):
        """Test user prompt includes CloudWatch logs."""
        event = {"exception": {"values": []}}
        logs = "2024-10-29T15:00:00Z ERROR: panic: runtime error: invalid memory address\n"
        prompt = build_user_prompt(
            sentry_event=event,
            cloudwatch_logs=logs,
        )

        assert "Related Logs" in prompt
        assert "invalid memory address" in prompt


# RECOMMENDATION SCHEMA


class TestRecommendationSchema:
    def test_recommendation_from_claude_response(self):
        """Test creating Recommendation from Claude response."""
        claude_response = {
            "summary": "Null pointer in alerts collector",
            "suggested_fix": "Add null check on line 42",
            "files_to_inspect": ["alerts.go"],
            "related_code_paths": ["internal/collector/alerts/"],
            "follow_up_actions": ["review", "test", "monitor"],
            "is_known_issue": False,
        }

        rec = Recommendation(**claude_response)
        assert rec.summary == "Null pointer in alerts collector"
        assert len(rec.files_to_inspect) == 1
        assert len(rec.follow_up_actions) == 3

    def test_recommendation_validation(self):
        """Test Recommendation requires all fields."""
        incomplete = {"summary": "test"}  # Missing fields

        with pytest.raises(ValueError):
            Recommendation(**incomplete)
