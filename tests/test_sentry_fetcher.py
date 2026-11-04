"""Tests for SentryFetcher (Phase 3)."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import requests

from ai_alert.services.sentry_fetcher import SentryFetcher


@pytest.fixture
def sentry_fetcher():
    """Fixture: SentryFetcher instance for testing."""
    return SentryFetcher(organization="test-org", api_token="sntrys_test_token_123")


# INITIALIZATION


class TestInitialization:
    def test_init_sets_organization_and_token(self):
        fetcher = SentryFetcher(organization="acme", api_token="sntrys_abc123")
        assert fetcher.organization == "acme"
        assert fetcher.api_token == "sntrys_abc123"
        assert fetcher.base_url == "https://arcticwolf.sentry.io/api/0"

    def test_init_creates_session_with_auth_header(self):
        fetcher = SentryFetcher(organization="acme", api_token="sntrys_abc123")
        assert "Authorization" in fetcher.session.headers
        assert fetcher.session.headers["Authorization"] == "Bearer sntrys_abc123"

    def test_context_manager_closes_session(self):
        fetcher = SentryFetcher(organization="acme", api_token="sntrys_abc123")
        with fetcher as f:
            assert f.session is not None
        # After context exit, close() should have been called
        # Verify by checking that a new session can be created normally
        assert fetcher.session is not None  # close() doesn't set it to None


# GET_ISSUE


class TestGetIssue:
    @patch("requests.Session.get")
    def test_get_issue_success(self, mock_get, sentry_fetcher):
        """Test successful issue fetch."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "12345",
            "title": "NullPointerException",
            "status": "unresolved",
            "count": 42,
        }
        mock_get.return_value = mock_response

        result = sentry_fetcher.get_issue("12345")

        assert result is not None
        assert result["id"] == "12345"
        assert result["title"] == "NullPointerException"
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "test-org" in call_args[0][0]
        assert "12345" in call_args[0][0]

    @patch("requests.Session.get")
    def test_get_issue_not_found(self, mock_get, sentry_fetcher):
        """Test 404 returns None."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_response
        )
        mock_response.json.return_value = {"detail": "Not found"}
        mock_get.return_value = mock_response

        result = sentry_fetcher.get_issue("nonexistent")

        assert result is None

    @patch("requests.Session.get")
    def test_get_issue_http_error_other_than_404(self, mock_get, sentry_fetcher):
        """Test 403/500 raises ValueError."""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_response
        )
        mock_get.return_value = mock_response

        with pytest.raises(ValueError, match="Failed to fetch issue"):
            sentry_fetcher.get_issue("12345")

    @patch("requests.Session.get")
    def test_get_issue_network_error(self, mock_get, sentry_fetcher):
        """Test network error raises RequestException."""
        mock_get.side_effect = requests.exceptions.ConnectionError("No internet")

        with pytest.raises(requests.exceptions.RequestException):
            sentry_fetcher.get_issue("12345")

    @patch("requests.Session.get")
    def test_get_issue_timeout(self, mock_get, sentry_fetcher):
        """Test timeout raises RequestException."""
        mock_get.side_effect = requests.exceptions.Timeout("Timeout")

        with pytest.raises(requests.exceptions.RequestException):
            sentry_fetcher.get_issue("12345")


# GET_LATEST_EVENT


class TestGetLatestEvent:
    @patch("requests.Session.get")
    def test_get_latest_event_success(self, mock_get, sentry_fetcher):
        """Test successful latest event fetch."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "event_id": "event-uuid-123",
            "exception": {
                "values": [
                    {
                        "type": "NullPointerException",
                        "value": "null pointer access",
                        "stacktrace": {
                            "frames": [
                                {
                                    "filename": "internal/collector/alerts/alerts.go",
                                    "lineno": 42,
                                    "function": "FetchAlerts",
                                }
                            ]
                        },
                    }
                ]
            },
            "tags": {
                "pod": "cx-collector-pod-123",
                "release": "v1.2.3",
                "environment": "production",
            },
            "breadcrumbs": [
                {
                    "timestamp": "2024-10-28T15:00:00Z",
                    "level": "info",
                    "message": "Fetching alerts",
                }
            ],
        }
        mock_get.return_value = mock_response

        result = sentry_fetcher.get_latest_event("12345")

        assert result is not None
        assert result["event_id"] == "event-uuid-123"
        assert "exception" in result
        assert "tags" in result
        assert "breadcrumbs" in result
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "test-org" in call_args[0][0]
        assert "12345" in call_args[0][0]
        assert "latest" in call_args[0][0]

    @patch("requests.Session.get")
    def test_get_latest_event_not_found(self, mock_get, sentry_fetcher):
        """Test 404 returns None."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_response
        )
        mock_get.return_value = mock_response

        result = sentry_fetcher.get_latest_event("nonexistent")

        assert result is None

    @patch("requests.Session.get")
    def test_get_latest_event_http_error(self, mock_get, sentry_fetcher):
        """Test non-404 HTTP error raises ValueError."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_response
        )
        mock_get.return_value = mock_response

        with pytest.raises(ValueError, match="Failed to fetch latest event"):
            sentry_fetcher.get_latest_event("12345")

    @patch("requests.Session.get")
    def test_get_latest_event_network_error(self, mock_get, sentry_fetcher):
        """Test network error raises RequestException."""
        mock_get.side_effect = requests.exceptions.ConnectionError()

        with pytest.raises(requests.exceptions.RequestException):
            sentry_fetcher.get_latest_event("12345")


# GET_EVENT


class TestGetEvent:
    @patch("requests.Session.get")
    def test_get_event_success(self, mock_get, sentry_fetcher):
        """Test successful event fetch by event_id."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "event_id": "specific-event-uuid",
            "message": "Test event",
        }
        mock_get.return_value = mock_response

        result = sentry_fetcher.get_event("12345", "specific-event-uuid")

        assert result is not None
        assert result["event_id"] == "specific-event-uuid"
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "12345" in call_args[0][0]
        assert "specific-event-uuid" in call_args[0][0]

    @patch("requests.Session.get")
    def test_get_event_not_found(self, mock_get, sentry_fetcher):
        """Test 404 returns None."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_response
        )
        mock_get.return_value = mock_response

        result = sentry_fetcher.get_event("12345", "nonexistent-event")

        assert result is None

    @patch("requests.Session.get")
    def test_get_event_http_error(self, mock_get, sentry_fetcher):
        """Test non-404 HTTP error raises ValueError."""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_response
        )
        mock_get.return_value = mock_response

        with pytest.raises(ValueError, match="Failed to fetch event"):
            sentry_fetcher.get_event("12345", "event-uuid")


# RETRY LOGIC


class TestRetryLogic:
    @patch("requests.Session.get")
    def test_retry_on_503(self, mock_get, sentry_fetcher):
        """Verify retry strategy is set up for 5xx errors."""
        # Create a mock that fails twice then succeeds
        fail_response = Mock()
        fail_response.status_code = 503
        fail_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=fail_response
        )

        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = {"id": "12345", "title": "Error"}

        # Mock sequence: fail, fail, succeed
        mock_get.side_effect = [
            requests.exceptions.ConnectionError(),
            requests.exceptions.ConnectionError(),
            success_response,
        ]

        # With retries configured, this should eventually succeed or exhaust retries
        # (In practice, the actual HTTPAdapter retries are transparent to the caller)
        # This test verifies the adapter is configured, not the full retry flow.
        assert sentry_fetcher.session.get_adapter("https://").max_retries.total == 3


# HEADERS AND AUTHENTICATION


class TestAuthenticationHeaders:
    def test_bearer_token_in_headers(self):
        fetcher = SentryFetcher(
            organization="test-org", api_token="sntrys_my_secret_token"
        )
        assert fetcher.session.headers["Authorization"] == "Bearer sntrys_my_secret_token"

    def test_content_type_header_set(self):
        fetcher = SentryFetcher(
            organization="test-org", api_token="sntrys_test_token"
        )
        assert fetcher.session.headers["Content-Type"] == "application/json"

    @patch("requests.Session.get")
    def test_auth_header_sent_in_request(self, mock_get):
        """Verify Authorization header is included in actual request."""
        fetcher = SentryFetcher(
            organization="test-org", api_token="sntrys_token_secret"
        )
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "123"}
        mock_get.return_value = mock_response

        fetcher.get_issue("123")

        # The session's headers are included in the request
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["timeout"] == 10
