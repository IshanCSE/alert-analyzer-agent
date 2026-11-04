# Phase 2 Completion Checklist

✅ **Phase 2: Local Storage (SQLite) — COMPLETE**

## Files Created / Changed

- ✅ `ai_alert/store.py` — `Store` class (new)
- ✅ `tests/test_store.py` — 25 unit tests, all passing (new)
- ✅ `ai_alert/__init__.py` — exports `Store`
- ✅ `ai_alert/cli.py` — `status` command now reports real counts from `Store.get_stats()` instead of a TODO stub

## What `Store` Does

`ai_alert/store.py` wraps a `sqlite3` connection and owns schema creation plus all CRUD operations defined in the plan's "Key Services" section.

### Schema

- **`alerts`** — one row per Sentry issue seen. `sentry_issue_id` is `UNIQUE NOT NULL` (the dedup key from the plan). Indexed on `sentry_issue_id`, `status`, and `received_at`.
- **`analyses`** — one row per completed analysis, `UNIQUE(alert_id)` (one analysis per alert), `FOREIGN KEY (alert_id) REFERENCES alerts(id) ON DELETE CASCADE` so deleting an alert cleans up its analysis. `recommendation_json` stores the `Recommendation` Pydantic model as JSON text.

Schema is created with `CREATE TABLE IF NOT EXISTS` on every `Store()` construction — safe to call repeatedly, no separate migration step needed yet.

### CRUD Methods

| Method | Purpose |
|---|---|
| `save_alert(alert)` | Insert, or upsert status/last_error if the id already exists |
| `get_alert_by_sentry_id(id)` | Dedup lookup — the primary check before analyzing |
| `get_alert_by_id(id)` | Lookup by internal UUID |
| `list_alerts(status=None, limit=100, offset=0)` | Paginated list, optional status filter |
| `count_alerts(status=None)` | Count for `status`/stats |
| `update_alert_status(id, status, error_msg=None)` | Transition status, e.g. `pending` → `analyzing` → `analyzed`/`failed` |
| `delete_alert(id)` | Removes alert + cascades to its analysis |
| `save_analysis(analysis)` | Persists the `Analysis`, serializing `recommendation` to JSON |
| `get_analysis_by_alert_id(id)` | Latest analysis for an alert |
| `get_analysis_by_id(id)` | Lookup by analysis UUID |
| `list_analyses(limit=100, offset=0)` | Paginated list of all analyses |
| `delete_analysis(id)` | Remove a single analysis |
| `get_stats()` | Dict of counts by status + total analyses — backs `ai-alert status` |

`Store` is also a context manager (`with Store(...) as store:`), matching how it's used in `cli.py`.

## Design Notes

- **Dedup key enforcement is a DB constraint, not just application logic** — `sentry_issue_id UNIQUE NOT NULL` means a duplicate `save_alert()` call raises `sqlite3.IntegrityError` rather than silently double-inserting. The `Analyzer` (Phase 4) is expected to call `get_alert_by_sentry_id()` first and skip analysis if found, per the plan's dedup flow.
- **Foreign key enforcement is on** (`PRAGMA foreign_keys = ON`) so `save_analysis()` for a non-existent `alert_id` fails loudly instead of leaving an orphaned row.
- **No ORM** — plain `sqlite3` + `Row` factory, matching the plan's "minimal ORM" preference. `Recommendation` round-trips through `model_dump_json()` / re-parsing with Pydantic, so nested fields survive intact.
- **In-memory and file-backed use the same class** — `Store(db_path=":memory:")` for tests, `Store(db_path="~/.ai-alert/data.db")` (expanded by `Config`) for real use. Parent directories are created automatically for file-backed paths.

## Verification

Since Poetry and Python 3.11+ are still not installed on this machine (see [PHASE_1_CHECKLIST.md](PHASE_1_CHECKLIST.md)), Phase 2 was verified with a throwaway venv built from the system Python 3.9 interpreter, pointed at the public PyPI index (the machine's default pip index is unreachable), with pydantic/pytest/click/loguru/pydantic-settings/pyyaml installed:

```bash
python3 -m venv .venv-verify
.venv-verify/bin/pip install --index-url https://pypi.org/simple \
    pydantic pydantic-settings pyyaml click loguru pytest
.venv-verify/bin/python -m pytest tests/ -v -o addopts=""
```

Result: **44 passed** (19 from Phase 1 + 25 new `test_store.py` tests), including:
- Schema creation/idempotency
- Save/get/list/count/update/delete for alerts
- Dedup constraint violation on duplicate `sentry_issue_id`
- Upsert behavior (status/last_error update on re-save)
- Save/get/list/delete for analyses, including `Recommendation` JSON round-trip
- Cascade delete (alert → analysis)
- Foreign-key rejection when saving an analysis for a nonexistent alert
- `get_stats()` counts
- File-backed persistence across two separate `Store` instances (directory auto-creation + data survives reconnect)

Also manually smoke-tested the CLI end-to-end (`ai-alert config-check` → `ai-alert status`) against a real file-backed SQLite DB in an isolated `$HOME`, confirming `status` now prints live counts instead of the old `[TODO] Add pending/analyzed counts after Phase 2` stub.

The throwaway `.venv-verify/` was deleted after verification — it is not part of the committed project. The project's real tests still run via `poetry run pytest` / `make test` once Poetry + Python 3.11+ are installed (see [GETTING_STARTED.md](GETTING_STARTED.md)).

## What's Next: Phase 3

**Phase 3: Sentry Fetcher** — Days 3-4

- `SentryFetcher` class using `requests`
- Methods: `get_issue()`, `get_latest_event()`
- Bearer token auth from `SENTRY_API_TOKEN`
- Error handling + retry logic
- CLI: `ai-alert analyze <issue-id>` fetches and pretty-prints the Sentry event (no Claude call yet)
- **Deliverable:** `ai-alert analyze 12345` prints Sentry event JSON

---

**Status:** Ready for Phase 3! 🚀
