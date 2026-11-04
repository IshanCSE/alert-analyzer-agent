"""CloudWatch Logs fetcher for enriching alert context (Phase 6)."""

from datetime import datetime, timedelta
from typing import Optional
import json

from ai_alert.logger import get_logger

logger = get_logger("cloudwatch_fetcher")


class CloudWatchFetcher:
    """Fetches CloudWatch logs for a pod during a time window (best-effort)."""

    def __init__(
        self,
        region: str = "us-west-2",
        log_group_prefix: str = "/eks/cx-collector",
        lookback_minutes: int = 5,
    ):
        """
        Initialize CloudWatchFetcher.

        Args:
            region: AWS region (default: us-west-2)
            log_group_prefix: CloudWatch log group prefix to search (default: /eks/cx-collector)
            lookback_minutes: How many minutes before/after event to search (default: 5)

        Note:
            Requires AWS credentials configured (via environment variables, IAM role, etc.)
            Gracefully skips if credentials unavailable (best-effort).
        """
        self.region = region
        self.log_group_prefix = log_group_prefix
        self.lookback_minutes = lookback_minutes

        # Try to import boto3 (optional dependency)
        try:
            import boto3
            self.boto3 = boto3
            self.client = boto3.client("logs", region_name=region)
            logger.info(f"CloudWatchFetcher initialized (region={region}, prefix={log_group_prefix})")
        except ImportError:
            logger.warning("boto3 not installed, CloudWatch integration disabled")
            self.boto3 = None
            self.client = None
        except Exception as e:
            logger.warning(f"Failed to initialize CloudWatch client: {e}")
            self.boto3 = None
            self.client = None

    def query_pod_logs(
        self,
        pod_id: str,
        error_timestamp: Optional[datetime] = None,
        limit: int = 100,
    ) -> Optional[str]:
        """
        Query CloudWatch logs for a pod around error timestamp.

        Args:
            pod_id: Pod identifier (e.g., "cx-collector-pod-abc123")
            error_timestamp: When the error occurred (defaults to now)
            limit: Max number of log lines to return (default: 100)

        Returns:
            Raw log lines as string, or None if unavailable

        Note:
            - Best-effort: returns None if credentials missing or query fails
            - Time window: ±lookback_minutes around error_timestamp
            - Filters logs for the pod_id
        """
        if not self.client:
            logger.debug("CloudWatch client not available, skipping log fetch")
            return None

        if not pod_id:
            logger.debug("No pod_id provided, skipping log fetch")
            return None

        try:
            if error_timestamp is None:
                error_timestamp = datetime.utcnow()

            # Calculate time window
            start_time = error_timestamp - timedelta(minutes=self.lookback_minutes)
            end_time = error_timestamp + timedelta(minutes=self.lookback_minutes)

            # Convert to milliseconds since epoch (CloudWatch requirement)
            start_ms = int(start_time.timestamp() * 1000)
            end_ms = int(end_time.timestamp() * 1000)

            logger.debug(
                f"Querying CloudWatch logs for pod={pod_id}, "
                f"start={start_time.isoformat()}, end={end_time.isoformat()}"
            )

            # Build query to search for pod_id in logs
            query = f'fields @timestamp, @message | filter @message like /{pod_id}/ | limit {limit}'

            # Start query
            response = self.client.start_query(
                logGroupName=self.log_group_prefix,
                startTime=start_ms,
                endTime=end_ms,
                queryString=query,
            )

            query_id = response["queryId"]
            logger.debug(f"Started CloudWatch query: {query_id}")

            # Poll for query completion (with timeout)
            import time
            max_wait_seconds = 30
            start = time.time()

            while time.time() - start < max_wait_seconds:
                result = self.client.get_query_results(queryId=query_id)
                status = result["status"]

                if status == "Complete":
                    # Extract log lines
                    log_lines = []
                    for record in result["results"]:
                        # Each record is a list of {"field": "key", "value": "value"}
                        line = " ".join([item["value"] for item in record])
                        log_lines.append(line)

                    logs_text = "\n".join(log_lines)
                    logger.info(f"Retrieved {len(log_lines)} log lines for pod {pod_id}")
                    return logs_text if logs_text else None

                elif status == "Failed":
                    logger.error(f"CloudWatch query failed: {result.get('statistics', {})}")
                    return None

                # Wait before polling again
                time.sleep(1)

            logger.warning(f"CloudWatch query timed out (> {max_wait_seconds}s)")
            return None

        except Exception as e:
            logger.warning(f"Failed to query CloudWatch logs: {e}")
            return None

    def extract_pod_from_tags(self, tags: dict) -> Optional[str]:
        """
        Extract pod ID from Sentry event tags.

        Args:
            tags: Sentry event tags dict

        Returns:
            Pod ID or None if not found
        """
        # Common Sentry tag names for pod/container
        pod_candidates = ["pod", "pod_id", "container", "container_id", "kubernetes_pod"]

        for key in pod_candidates:
            if key in tags:
                pod_id = tags[key]
                if pod_id:
                    logger.debug(f"Found pod_id from tag '{key}': {pod_id}")
                    return pod_id

        logger.debug("No pod ID found in tags")
        return None

    def close(self):
        """Close CloudWatch client."""
        if self.client:
            self.client = None
        logger.debug("CloudWatchFetcher closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
