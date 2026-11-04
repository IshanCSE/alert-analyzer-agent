"""Sentry REST API client for fetching issue and event details."""

from typing import Optional, Dict, Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ai_alert.logger import get_logger
from ai_alert.ca_bundle import get_ca_bundle

logger = get_logger("sentry_fetcher")


class SentryFetcher:
    """Client for Sentry REST API."""

    def __init__(self, organization: str, api_token: str, sentry_host: str = "arcticwolf.sentry.io"):
        """Initialize SentryFetcher.

        Args:
            organization: Sentry organization slug (e.g., 'arcticwolf')
            api_token: Sentry API token (sntrys_...) with scopes: event:read, org:read, project:read
            sentry_host: Sentry instance hostname (default: arcticwolf.sentry.io)
        """
        self.organization = organization
        self.api_token = api_token
        self.base_url = f"https://{sentry_host}/api/0"

        # Create session with retry strategy
        self.session = requests.Session()

        # Auto-discover and apply CA certificates (for corporate proxies/internal gateways)
        # Searches: env vars → project config → AWN certs → system certs
        ca_bundle = get_ca_bundle()
        if ca_bundle:
            self.session.verify = ca_bundle
            logger.debug(f"SentryFetcher using CA bundle: {ca_bundle}")

        retry_strategy = Retry(
            total=3,
            backoff_factor=1.0,  # 1s, 2s, 4s
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],  # only retry idempotent methods
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Set default headers
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            }
        )

    def get_issue(self, issue_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a Sentry issue by ID.

        Args:
            issue_id: Sentry issue ID (numeric)

        Returns:
            Issue object (dict) or None if not found / error

        Raises:
            requests.RequestException: On network error, timeout, or 5xx server error
            ValueError: On unexpected HTTP error (4xx, etc.)
        """
        url = f"{self.base_url}/organizations/{self.organization}/issues/{issue_id}/"

        try:
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            logger.debug(f"Fetched issue {issue_id}")
            return resp.json()
        except requests.exceptions.HTTPError as e:
            if resp.status_code == 404:
                logger.warning(f"Issue {issue_id} not found (404)")
                return None
            logger.error(f"HTTP error fetching issue {issue_id}: {e}")
            raise ValueError(f"Failed to fetch issue {issue_id}: {e}") from e
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error fetching issue {issue_id}: {e}")
            raise

    def get_latest_event(self, issue_id: str) -> Optional[Dict[str, Any]]:
        """Fetch the latest event for a Sentry issue.

        Args:
            issue_id: Sentry issue ID (numeric)

        Returns:
            Event object (dict) with stack trace, tags, breadcrumbs, or None if not found

        Raises:
            requests.RequestException: On network error, timeout, or 5xx server error
            ValueError: On unexpected HTTP error (4xx, etc.)
        """
        url = f"{self.base_url}/organizations/{self.organization}/issues/{issue_id}/events/latest/"

        try:
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            logger.debug(f"Fetched latest event for issue {issue_id}")
            return resp.json()
        except requests.exceptions.HTTPError as e:
            if resp.status_code == 404:
                logger.warning(f"Latest event for issue {issue_id} not found (404)")
                return None
            logger.error(f"HTTP error fetching latest event for issue {issue_id}: {e}")
            raise ValueError(f"Failed to fetch latest event for issue {issue_id}: {e}") from e
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error fetching latest event for issue {issue_id}: {e}")
            raise

    def get_event(
        self, issue_id: str, event_id: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch a specific event by issue ID and event ID.

        Args:
            issue_id: Sentry issue ID (numeric)
            event_id: Sentry event ID (UUID)

        Returns:
            Event object (dict) or None if not found

        Raises:
            requests.RequestException: On network error, timeout, or 5xx server error
            ValueError: On unexpected HTTP error (4xx, etc.)
        """
        url = f"{self.base_url}/organizations/{self.organization}/issues/{issue_id}/events/{event_id}/"

        try:
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            logger.debug(f"Fetched event {event_id} for issue {issue_id}")
            return resp.json()
        except requests.exceptions.HTTPError as e:
            if resp.status_code == 404:
                logger.warning(f"Event {event_id} for issue {issue_id} not found (404)")
                return None
            logger.error(f"HTTP error fetching event: {e}")
            raise ValueError(f"Failed to fetch event {event_id}: {e}") from e
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error fetching event: {e}")
            raise

    def close(self):
        """Close the session."""
        if self.session:
            self.session.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
