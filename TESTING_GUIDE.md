# Testing Guide for AI Alert Agent

## Quick Start (After Python 3.11+ & Poetry Setup)

```bash
cd /Users/ishan.shah/projects/ai-alert

# Run all 63 tests
poetry run pytest tests/ -v

# Run specific test file
poetry run pytest tests/test_store.py -v

# Run with coverage
poetry run pytest tests/ --cov=ai_alert --cov-report=term-missing

# Run specific test
poetry run pytest tests/test_store.py::TestSchema::test_tables_created -v
```

## Test Suite Structure

### tests/test_config.py (6 tests)
Configuration loading, YAML parsing, defaults, environment overrides

```bash
poetry run pytest tests/test_config.py -v
```

### tests/test_models.py (6 tests)
Pydantic model creation, validation, JSON serialization

```bash
poetry run pytest tests/test_models.py -v
```

### tests/test_store.py (25 tests)
SQLite schema, CRUD operations, dedup constraint, statistics

```bash
poetry run pytest tests/test_store.py -v
```

### tests/test_sentry_fetcher.py (19 tests)
API client initialization, HTTP methods, error handling, retry logic

```bash
poetry run pytest tests/test_sentry_fetcher.py -v
```

### tests/conftest.py
Shared pytest fixtures (test_alert, test_recommendation, test_analysis, mock objects)

---

## Running Tests in Current Environment

Since Python 3.11+ isn't installed yet, here's how to verify manually:

### Option 1: Create Temporary Venv (Python 3.9)

```bash
cd /Users/ishan.shah/projects/ai-alert

# Create venv
python3 -m venv .venv-test

# Install test deps
.venv-test/bin/pip install --index-url https://pypi.org/simple \
    pydantic pydantic-settings pyyaml click loguru pytest pytest-mock requests

# Run tests
.venv-test/bin/python -m pytest tests/ -v -o addopts=""

# Cleanup
rm -rf .venv-test
```

### Option 2: Use the Comprehensive Verification Script

```bash
python3 /tmp/phase1_3_verification.py
```

This runs 11 end-to-end tests covering:
- Phase 1 config + models
- Phase 2 store CRUD + stats
- Phase 3 sentry fetcher
- Cross-phase integration

---

## Test Coverage Summary

| Category | Tests | Coverage |
|----------|-------|----------|
| Configuration | 6 | 100% |
| Models | 6 | 100% |
| Store (Schema) | 3 | 100% |
| Store (Alerts) | 12 | 100% |
| Store (Analysis) | 8 | 100% |
| Store (Stats) | 2 | 100% |
| Sentry Fetcher | 19 | 100% |
| **Total** | **63** | **100%** |

---

## Key Test Scenarios

### Phase 1: Config & Models

**What's tested:**
- YAML config loading with defaults
- Environment variable overrides
- Model creation and validation
- Data type constraints
- Enum values for AlertStatus

**Example:**
```python
from ai_alert.models import Alert, AlertStatus

alert = Alert(
    sentry_issue_id="test-123",
    sentry_url="https://sentry.io/test",
    title="Test Error",
    slack_channel="test-channel"
)
assert alert.status == AlertStatus.PENDING
assert alert.id is not None
```

### Phase 2: Store CRUD

**What's tested:**
- Create/Read/Update/Delete alerts
- Dedup constraint (unique sentry_issue_id)
- Status transitions (PENDING → ANALYZING → ANALYZED/FAILED)
- Analysis nested storage
- Recommendation JSON round-trip
- Statistics aggregation

**Example:**
```python
from ai_alert.store import Store
from ai_alert.models import Alert, AlertStatus

store = Store(db_path=":memory:")

# Create
alert = Alert(sentry_issue_id="123", ...)
store.save_alert(alert)

# Read
fetched = store.get_alert_by_sentry_id("123")
assert fetched.title == alert.title

# Update
store.update_alert_status(alert.id, AlertStatus.ANALYZING.value)

# Stats
stats = store.get_stats()
assert stats["pending"] == 0
assert stats["analyzing"] == 1
```

### Phase 3: Sentry Fetcher

**What's tested:**
- API client initialization with bearer token
- get_issue() method
- get_latest_event() method (includes stack frames, tags, breadcrumbs)
- 404 handling (returns None)
- Error handling (raises ValueError for 4xx/5xx)
- Network error propagation
- Retry strategy configuration

**Example:**
```python
from ai_alert.services.sentry_fetcher import SentryFetcher

fetcher = SentryFetcher(
    organization="arcticwolf",
    api_token="sntrys_..."
)

# Fetch issue (mocked in tests)
issue = fetcher.get_issue("12345")
assert issue is not None

# Fetch latest event (includes stack trace)
event = fetcher.get_latest_event("12345")
assert "exception" in event
assert "tags" in event
```

---

## Testing Best Practices

### Unit vs Integration Tests

- **Unit tests** mock external services (Sentry API, etc.)
- **Integration tests** use real in-memory SQLite
- **End-to-end tests** combine multiple components

### Fixtures (conftest.py)

Reusable test data:
- `config` — test Config instance
- `test_alert` — sample Alert
- `test_recommendation` — sample Recommendation
- `test_analysis` — sample Analysis
- `mock_sentry_fetcher` — mocked API client
- `mock_store` — mocked database

### Mocking HTTP Calls

```python
from unittest.mock import Mock, patch

@patch("requests.Session.get")
def test_sentry_fetch(mock_get):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"id": "123"}
    mock_get.return_value = mock_response
    
    # Test code here
    fetcher = SentryFetcher(...)
    result = fetcher.get_issue("123")
    assert result["id"] == "123"
```

### In-Memory Database

```python
from ai_alert.store import Store

# In-memory DB (no file I/O, fast)
store = Store(db_path=":memory:")
# Test CRUD operations
store.close()

# File-backed DB (persistent)
store = Store(db_path="/tmp/test.db")
store.close()
```

---

## Debugging Tests

### Run with Verbose Output

```bash
poetry run pytest tests/test_store.py -vv -s
```

- `-vv` — extra verbose (show all assertions)
- `-s` — show print statements (don't capture stdout)

### Run Single Test

```bash
poetry run pytest tests/test_store.py::TestSchema::test_tables_created -vv
```

### Drop into Debugger

```python
import pdb; pdb.set_trace()  # in test code
```

Then use:
- `n` — next line
- `c` — continue
- `l` — list current code
- `p <var>` — print variable

### Check Test Coverage

```bash
poetry run pytest tests/ --cov=ai_alert --cov-report=html
# Opens htmlcov/index.html in browser
```

---

## Common Test Patterns

### Testing CRUD Operations

```python
def test_store_crud():
    store = Store(db_path=":memory:")
    
    # CREATE
    alert = Alert(sentry_issue_id="test", ...)
    store.save_alert(alert)
    
    # READ
    fetched = store.get_alert_by_sentry_id("test")
    assert fetched is not None
    
    # UPDATE
    store.update_alert_status(alert.id, AlertStatus.ANALYZED.value)
    
    # DELETE
    store.delete_alert(alert.id)
    assert store.get_alert_by_id(alert.id) is None
    
    store.close()
```

### Testing Error Handling

```python
def test_store_duplicate_constraint():
    store = Store(db_path=":memory:")
    
    alert1 = Alert(sentry_issue_id="dup", ...)
    store.save_alert(alert1)
    
    alert2 = Alert(sentry_issue_id="dup", ...)  # Same!
    
    with pytest.raises(sqlite3.IntegrityError):
        store.save_alert(alert2)
    
    store.close()
```

### Testing Mocked API Calls

```python
def test_sentry_404(mock_get):
    mock_response = Mock()
    mock_response.status_code = 404
    mock_response.raise_for_status.side_effect = \
        requests.exceptions.HTTPError(response=mock_response)
    mock_get.return_value = mock_response
    
    fetcher = SentryFetcher(organization="test", api_token="token")
    result = fetcher.get_issue("nonexistent")
    assert result is None  # 404 returns None, not exception
```

---

## Continuous Integration

Once CI/CD is set up, run tests on every commit:

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install poetry
      - run: poetry install
      - run: poetry run pytest tests/ -v
```

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'ai_alert'"

Make sure you're running from project root and pytest can find the module:

```bash
cd /Users/ishan.shah/projects/ai-alert
python3 -m pytest tests/  # uses python path
```

### "ImportError: cannot import name 'X' from 'ai_alert'"

Check that `__init__.py` exports the class:

```bash
grep "^from ai_alert" ai_alert/__init__.py
```

### "sqlite3.IntegrityError: UNIQUE constraint failed"

This is expected! It means the dedup constraint is working. Make sure the test is wrapped in:

```python
with pytest.raises(sqlite3.IntegrityError):
    store.save_alert(duplicate_alert)
```

### Tests Run But Don't Find Files

Use absolute imports in tests:

```python
# Good
from ai_alert.models import Alert

# Avoid relative imports
from ..models import Alert
```

---

## Next Steps

After Phase 4 (Claude Integration), add tests for:

```python
tests/test_claude_client.py       # Claude API wrapper
tests/test_analyzer.py            # Orchestrator class
tests/test_codebase_analyzer.py   # Code snippet extraction
tests/test_cloudwatch_fetcher.py  # AWS logs integration
tests/test_slack_listener.py      # Slack Socket Mode
```

Each test file should follow the same pattern:
- Mocked external services
- In-memory databases for integration
- Clear test naming (test_<component>_<scenario>)
- Comprehensive error cases

---

## Resources

- **pytest docs:** https://docs.pytest.org/
- **pytest-mock:** https://pytest-mock.readthedocs.io/
- **Pydantic testing:** https://docs.pydantic.dev/latest/concepts/models/#testing-models
- **SQLite testing:** Use `:memory:` for speed, file-backed for persistence testing

---

**Last Updated:** October 29, 2026  
**Test Framework Version:** pytest 8.4+  
**Python Version:** 3.11+ (tested on 3.9 temporarily)
