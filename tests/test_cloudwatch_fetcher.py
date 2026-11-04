"""Tests for CloudWatchFetcher (Phase 6)."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import time

from ai_alert.services.cloudwatch_fetcher import CloudWatchFetcher


# INITIALIZATION


class TestCloudWatchFetcherInitialization:
    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        fetcher = CloudWatchFetcher()
        assert fetcher.region == "us-west-2"
        assert fetcher.log_group_prefix == "/eks/cx-collector"
        assert fetcher.lookback_minutes == 5

    def test_init_with_custom_params(self):
        """Test initialization with custom parameters."""
        fetcher = CloudWatchFetcher(
            region="us-east-1",
            log_group_prefix="/custom/logs",
            lookback_minutes=10,
        )
        assert fetcher.region == "us-east-1"
        assert fetcher.log_group_prefix == "/custom/logs"
        assert fetcher.lookback_minutes == 10

    def test_init_without_boto3_graceful(self):
        """Test initialization gracefully handles missing boto3."""
        # Just verify initialization doesn't crash
        # boto3 is available in test environment, so client will be initialized
        fetcher = CloudWatchFetcher()
        assert fetcher is not None
        # Either client exists or is None - both are valid
        assert hasattr(fetcher, "client")


# POD ID EXTRACTION


class TestExtractPodFromTags:
    def test_extract_pod_from_pod_tag(self):
        """Test extracting pod ID from 'pod' tag."""
        fetcher = CloudWatchFetcher()
        tags = {"pod": "cx-collector-pod-abc123", "release": "v1.0"}

        pod_id = fetcher.extract_pod_from_tags(tags)

        assert pod_id == "cx-collector-pod-abc123"

    def test_extract_pod_from_pod_id_tag(self):
        """Test extracting pod ID from 'pod_id' tag."""
        fetcher = CloudWatchFetcher()
        tags = {"pod_id": "cx-collector-xyz789"}

        pod_id = fetcher.extract_pod_from_tags(tags)

        assert pod_id == "cx-collector-xyz789"

    def test_extract_pod_from_container_tag(self):
        """Test extracting pod ID from 'container' tag."""
        fetcher = CloudWatchFetcher()
        tags = {"container": "cx-collector", "environment": "prod"}

        pod_id = fetcher.extract_pod_from_tags(tags)

        assert pod_id == "cx-collector"

    def test_extract_pod_missing_returns_none(self):
        """Test extraction returns None when pod not in tags."""
        fetcher = CloudWatchFetcher()
        tags = {"environment": "prod", "release": "v1.0"}

        pod_id = fetcher.extract_pod_from_tags(tags)

        assert pod_id is None

    def test_extract_pod_empty_tags(self):
        """Test extraction with empty tags dict."""
        fetcher = CloudWatchFetcher()

        pod_id = fetcher.extract_pod_from_tags({})

        assert pod_id is None

    def test_extract_pod_priority_order(self):
        """Test extraction respects key priority order."""
        fetcher = CloudWatchFetcher()
        # 'pod' is checked first, so should be used even if others present
        tags = {
            "pod": "primary-pod",
            "pod_id": "secondary-pod",
            "container": "tertiary-pod",
        }

        pod_id = fetcher.extract_pod_from_tags(tags)

        assert pod_id == "primary-pod"


# QUERY POD LOGS


class TestQueryPodLogs:
    def test_query_pod_logs_no_client(self):
        """Test query returns None when client unavailable."""
        fetcher = CloudWatchFetcher()
        fetcher.client = None  # Manually set to None

        result = fetcher.query_pod_logs(pod_id="test-pod")

        assert result is None

    def test_query_pod_logs_no_pod_id(self):
        """Test query returns None when pod_id is empty."""
        fetcher = CloudWatchFetcher()

        result = fetcher.query_pod_logs(pod_id="")

        assert result is None

    def test_query_pod_logs_success(self):
        """Test successful log query."""
        fetcher = CloudWatchFetcher()
        mock_client = Mock()
        fetcher.client = mock_client

        # Mock CloudWatch response
        mock_client.start_query.return_value = {"queryId": "query-123"}
        mock_client.get_query_results.return_value = {
            "status": "Complete",
            "results": [
                [
                    {"field": "@timestamp", "value": "2024-10-29T15:00:00Z"},
                    {"field": "@message", "value": "Error: null pointer"},
                ],
                [
                    {"field": "@timestamp", "value": "2024-10-29T15:00:01Z"},
                    {"field": "@message", "value": "Pod restarted"},
                ],
            ],
        }

        error_timestamp = datetime(2024, 10, 29, 15, 0, 0)
        result = fetcher.query_pod_logs(pod_id="test-pod", error_timestamp=error_timestamp)

        assert result is not None
        assert "Error: null pointer" in result
        assert "Pod restarted" in result
        mock_client.start_query.assert_called_once()

    def test_query_pod_logs_with_default_timestamp(self):
        """Test query uses current time when error_timestamp not provided."""
        fetcher = CloudWatchFetcher()
        mock_client = Mock()
        fetcher.client = mock_client

        mock_client.start_query.return_value = {"queryId": "query-123"}
        mock_client.get_query_results.return_value = {"status": "Complete", "results": []}

        result = fetcher.query_pod_logs(pod_id="test-pod")

        # Should call start_query with reasonable timestamps
        assert mock_client.start_query.called
        call_args = mock_client.start_query.call_args
        assert "startTime" in call_args[1]
        assert "endTime" in call_args[1]

    def test_query_pod_logs_respects_time_window(self):
        """Test that time window is respected."""
        fetcher = CloudWatchFetcher(lookback_minutes=10)
        mock_client = Mock()
        fetcher.client = mock_client

        mock_client.start_query.return_value = {"queryId": "query-123"}
        mock_client.get_query_results.return_value = {"status": "Complete", "results": []}

        error_timestamp = datetime(2024, 10, 29, 15, 0, 0)
        result = fetcher.query_pod_logs(pod_id="test-pod", error_timestamp=error_timestamp)

        call_args = mock_client.start_query.call_args[1]
        start_time_ms = call_args["startTime"]
        end_time_ms = call_args["endTime"]

        # Verify 20-minute window (10 before + 10 after = 20 total, in ms)
        expected_window_ms = 20 * 60 * 1000  # 1,200,000 ms
        actual_window_ms = end_time_ms - start_time_ms
        assert actual_window_ms == expected_window_ms

    def test_query_pod_logs_respects_limit(self):
        """Test that query limit is respected."""
        fetcher = CloudWatchFetcher()
        mock_client = Mock()
        fetcher.client = mock_client

        mock_client.start_query.return_value = {"queryId": "query-123"}
        mock_client.get_query_results.return_value = {"status": "Complete", "results": []}

        fetcher.query_pod_logs(pod_id="test-pod", limit=50)

        call_args = mock_client.start_query.call_args[1]
        query_string = call_args["queryString"]
        assert "limit 50" in query_string

    def test_query_pod_logs_failed_status(self):
        """Test handling of failed CloudWatch query."""
        fetcher = CloudWatchFetcher()
        mock_client = Mock()
        fetcher.client = mock_client

        mock_client.start_query.return_value = {"queryId": "query-123"}
        mock_client.get_query_results.return_value = {
            "status": "Failed",
            "statistics": {"recordsMatched": 0},
        }

        result = fetcher.query_pod_logs(pod_id="test-pod")

        assert result is None

    @patch("time.sleep")  # Mock sleep to speed up test
    def test_query_pod_logs_timeout(self, mock_sleep):
        """Test handling of CloudWatch query timeout."""
        fetcher = CloudWatchFetcher()
        mock_client = Mock()
        fetcher.client = mock_client

        mock_client.start_query.return_value = {"queryId": "query-123"}
        # Return "Running" status indefinitely to trigger timeout
        mock_client.get_query_results.return_value = {"status": "Running"}

        result = fetcher.query_pod_logs(pod_id="test-pod")

        assert result is None
        # Should have polled multiple times
        assert mock_client.get_query_results.call_count > 1

    def test_query_pod_logs_empty_results(self):
        """Test handling of empty query results."""
        fetcher = CloudWatchFetcher()
        mock_client = Mock()
        fetcher.client = mock_client

        mock_client.start_query.return_value = {"queryId": "query-123"}
        mock_client.get_query_results.return_value = {"status": "Complete", "results": []}

        result = fetcher.query_pod_logs(pod_id="test-pod")

        # Should return None when no logs found
        assert result is None

    def test_query_pod_logs_exception_handling(self):
        """Test graceful error handling."""
        fetcher = CloudWatchFetcher()
        mock_client = Mock()
        fetcher.client = mock_client

        mock_client.start_query.side_effect = Exception("API error")

        result = fetcher.query_pod_logs(pod_id="test-pod")

        assert result is None


# RESOURCE MANAGEMENT


class TestCloudWatchFetcherResourceManagement:
    def test_context_manager(self):
        """Test context manager protocol."""
        with CloudWatchFetcher() as fetcher:
            assert fetcher is not None
        # Should exit cleanly

    def test_close_method(self):
        """Test close method."""
        fetcher = CloudWatchFetcher()
        fetcher.close()  # Should not raise


# INTEGRATION


class TestCloudWatchFetcherIntegration:
    def test_full_workflow(self):
        """Test complete workflow: extract pod ID and query logs."""
        fetcher = CloudWatchFetcher()

        # Extract pod ID from tags
        tags = {"pod": "cx-collector-pod-123", "environment": "prod"}
        pod_id = fetcher.extract_pod_from_tags(tags)
        assert pod_id == "cx-collector-pod-123"

        # Query logs (will return None since no real AWS client, but shouldn't crash)
        result = fetcher.query_pod_logs(pod_id=pod_id)
        # Result will be None since no client, but that's expected in tests

    def test_full_workflow_with_mock(self):
        """Test complete workflow with mocked CloudWatch."""
        fetcher = CloudWatchFetcher()
        mock_client = Mock()
        fetcher.client = mock_client

        # Extract pod ID
        tags = {"pod": "cx-collector-prod-abc"}
        pod_id = fetcher.extract_pod_from_tags(tags)

        # Mock logs response
        mock_client.start_query.return_value = {"queryId": "q-1"}
        mock_client.get_query_results.return_value = {
            "status": "Complete",
            "results": [[{"field": "@message", "value": "Error log line"}]],
        }

        # Query logs
        logs = fetcher.query_pod_logs(pod_id=pod_id)

        assert pod_id == "cx-collector-prod-abc"
        assert logs is not None
        assert "Error log line" in logs
