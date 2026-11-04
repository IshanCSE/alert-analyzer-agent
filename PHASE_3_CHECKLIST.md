# Phase 3 Completion Checklist

✅ **Phase 3: Sentry Fetcher — COMPLETE**

## Files Created / Changed

- ✅ `ai_alert/services/sentry_fetcher.py` — `SentryFetcher` class (new)
- ✅ `tests/test_sentry_fetcher.py` — 19 unit tests, all passing (new)
- ✅ `ai_alert/cli.py` — `analyze` command wired to fetch and display Sentry event data
- ✅ `tests/conftest.py` — added fixture for consistency
- ✅ `README.md` — Phase 3 marked complete in the implementation table

## What `SentryFetcher` Does

`ai_alert/services/sentry_fetcher.py` provides a REST API client for Sentry with these key features:

### Methods

| Method | Purpose |
|---|---|
| `get_issue(issue_id)` | Fetch a Sentry issue by numeric ID |
| `get_latest_event(issue_id)` | Fetch the most recent event for an issue (includes stack trace, tags, breadcrumbs) |
| `get_event(issue_id, event_id)` | Fetch a specific event by issue + event IDs |

### Features

- **Bearer Token Auth:** Reads `SENTRY_API_TOKEN` from environment, uses it for all HTTP requests (`Authorization: Bearer <token>`)
- **Retry Logic:** Uses urllib3 `Retry` with exponential backoff (3 total attempts, backoff factor 1.0s → 1s/2s/4s) for transient failures (429, 5xx)
- **Error Handling:** 
  - 404 returns `None` (issue/event not found)
  - Other 4xx/5xx raises `ValueError` with descriptive message
  - Network errors raise `RequestException` to bubble up to caller
- **Context Manager:** Supports `with SentryFetcher(...) as fetcher:` for clean resource management
- **Timeout:** All requests have a 10-second timeout to prevent hanging

### Organization & Token

Constructor requires:
- `organization` (e.g., `"arcticwolf"`) — the Sentry org slug
- `api_token` (e.g., `"sntrys_..."`) — a Sentry API token with scopes `event:read`, `org:read`, `project:read`

Base URL is hard-coded to `https://sentry.io/api/0`.

## CLI Integration

The `ai-alert analyze <issue-id>` command now:

1. **Reads config** (organization from `config.yaml`)
2. **Reads token** from `SENTRY_API_TOKEN` environment variable
3. **Fetches issue details** via `SentryFetcher.get_issue()`
4. **Fetches latest event** via `SentryFetcher.get_latest_event()`
5. **Pretty-prints** the event as formatted JSON

Example usage (once Poetry + Python 3.11+ are installed):

```bash
export SENTRY_API_TOKEN="sntrys_..."
poetry run ai-alert analyze 12345
```

Output:
```
📊 Analyzing Sentry issue 12345...
🔍 Fetching issue details from Sentry...
📋 Fetching latest event...

✅ Fetched event from Sentry

Event Details:
================================================================================
{
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
              "function": "FetchAlerts"
            }
          ]
        }
      }
    ]
  },
  "tags": {
    "pod": "cx-collector-pod-123",
    "release": "v1.2.3",
    "environment": "production"
  },
  "breadcrumbs": [...]
}
```

## Test Coverage

19 tests in `test_sentry_fetcher.py`:

- **Initialization** (3): org/token storage, auth headers, context manager
- **get_issue** (5): success, 404 → None, non-404 error → ValueError, network error, timeout
- **get_latest_event** (4): success, 404 → None, HTTP error, network error
- **get_event** (3): success, 404 → None, HTTP error
- **Retry Logic** (1): verifies retry strategy is configured on the session
- **Authentication** (3): bearer token in headers, content-type header, auth sent in requests

All 63 tests pass (6 Phase 1 config/models + 25 Phase 2 Store + 19 Phase 3 SentryFetcher + 13 models tests).

## Verification

Tested with throwaway venv (system Python 3.9 → public PyPI) after fixing `urllib3.Retry` API:

```bash
python3 -m venv .venv-phase3-test
.venv-phase3-test/bin/pip install --index-url https://pypi.org/simple \
    pydantic pydantic-settings pyyaml click loguru pytest pytest-mock requests
.venv-phase3-test/bin/python -m pytest tests/ -v -o addopts=""
```

**Result: 63 passed**

## Design Notes

- **Sentry API URL:** Hard-coded to `https://sentry.io/api/0` (the public SaaS Sentry). On-premises deployments (e.g., self-hosted Sentry) would need a different base URL — this can be made configurable in Phase 4+ if needed.
- **Bearer Token vs API Token:** The Sentry REST API uses bearer tokens (passed via `Authorization: Bearer <token>` header). Do not confuse with "API key" headers used by some Sentry SDKs.
- **Event Structure:** The returned event JSON includes the full `exception.values[].stacktrace.frames` array, which Phase 5 (Codebase Analysis) will use to correlate stack frames to local file:line locations.
- **Retry Strategy:** Only retries on idempotent GET requests with specific status codes (429, 5xx), not on 4xx errors or POST/PUT. This prevents infinite loops on auth failures.

## What's Next: Phase 4

**Phase 4: Claude Integration (Core Value)** — Days 4-6

- `ClaudeClient` class wrapping Anthropic SDK
- Build system prompt (cx-collector patterns + error taxonomy)
- Build user prompt from evidence bundle (Sentry event + optional CloudWatch logs + code snippets)
- Call Claude with `response_format={"type": "json_object"}` for structured `Recommendation` output
- Implement `Analyzer` orchestrator class that combines `SentryFetcher` + `ClaudeClient` + `Store`
- Wire into `ai-alert analyze <id>` to produce full `Analysis` + save to DB
- **Deliverable:** `ai-alert analyze <id>` outputs AI-generated root cause + recommendations, persists to SQLite

---

**Status:** Ready for Phase 4! 🚀
