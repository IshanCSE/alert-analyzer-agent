# Phase 8 Completion Checklist

✅ **Phase 8: Polish & Operations — COMPLETE**

**Date:** October 30, 2026
**Tests:** 11 new tests (all passing, 191 total: 180 Phase 1-7 + 11 Phase 8)
**Scope:** CLI management commands, macOS background daemon support, operational docs/tooling

---

## Files Created / Changed

- ✅ `ai_alert/cli.py` — Added `list`, `show`, `gc` commands (between `status` and the `daemon` group)
- ✅ `tests/test_cli.py` — 11 unit tests (new)
- ✅ `configs/com.ai-alert.daemon.plist` — macOS `launchd` service template (new)
- ✅ `configs/config.example.yaml` — Example YAML config with inline env var docs (new)
- ✅ `Makefile` — Rewritten with working targets matched to the real CLI/config layout
- ✅ `.env.example` — Rewritten with the actual required/optional env vars
- ✅ `README.md` — Phase 8 marked ✅ Complete; CLI reference, Makefile targets, launchd instructions, and env var docs corrected to match what's actually implemented

---

## What the New CLI Commands Do

### `ai-alert list`

Lists alerts from the local SQLite store.

| Option | Purpose |
|--------|---------|
| `--status` | Filter: `pending`, `analyzing`, `analyzed`, `failed`, or `all` (default) |
| `--limit` | Max rows to display (default 50) |
| `--config` | Path to config file |
| `--log-level` | Logging verbosity |

Output: one block per alert with a status emoji (⏳🔍✅❌), short ID, Sentry issue ID, title, status, received timestamp, and last error if present.

### `ai-alert show <alert-id>`

Shows full detail for a single alert plus its analysis (if one exists).

- Exits `1` with `✗ Alert {id} not found` if the ID doesn't resolve.
- Without an analysis: prints alert fields + `⏳ No analysis yet`.
- With an analysis: adds model, root cause, confidence, error category, affected component, tokens used, created-at, and the full `Recommendation` (summary, suggested fix, files to inspect, follow-up actions).

### `ai-alert gc`

Garbage-collects alerts older than a cutoff.

| Option | Purpose |
|--------|---------|
| `--days` | Delete alerts older than this many days (default 30) |
| `--dry-run` | Preview only — lists up to 10 matches + a count of the rest, never calls `delete_alert` |
| `--config` / `--log-level` | Same as other commands |

Implementation note: filters client-side (`store.list_alerts(limit=10000)` then a Python filter on `received_at`), since `Store` has no date-range query. Deletes are best-effort per-row — a single failed delete is logged as a warning and does not abort the rest of the batch.

---

## launchd Background Daemon

`configs/com.ai-alert.daemon.plist` lets the daemon run as a persistent macOS
background service instead of a foreground terminal process.

**Key settings:**
- `KeepAlive: true` + `ThrottleInterval: 5` — restarts the process if it crashes, with a 5s backoff
- `RunAtLoad: true` — starts automatically when the plist is loaded (including at login, if placed in `~/Library/LaunchAgents/`)
- `EnvironmentVariables` — carries `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `SENTRY_API_TOKEN`, `ANTHROPIC_API_KEY`, `AWS_PROFILE` (placeholder values — must be filled in before use, and the filled-in copy should **not** be committed)
- `StandardOutPath` / `StandardErrorPath` — logs to `~/.ai-alert/logs/daemon.{out,err}.log`
- Runs `poetry run ai-alert daemon start --foreground` under the hood — launchd's job *is* the foreground process; there's no separate background mode in the CLI itself

**Usage:**
```bash
cp configs/com.ai-alert.daemon.plist ~/Library/LaunchAgents/com.ai-alert.daemon.plist
# edit in real tokens/paths
launchctl load ~/Library/LaunchAgents/com.ai-alert.daemon.plist
launchctl unload ~/Library/LaunchAgents/com.ai-alert.daemon.plist   # to stop
```

---

## Makefile

Rewritten (via direct file write, since no prior committed Makefile existed to preserve — the project has never been through `git init`, so there was no history to lose). Targets:

| Target | Purpose |
|--------|---------|
| `help` (default) | Lists all targets |
| `install` | `poetry install --no-dev` |
| `dev` | `poetry install` (includes dev deps) |
| `test` | `poetry run pytest tests/ -v --tb=short` |
| `lint` | `poetry run ruff check ai_alert/ tests/` |
| `format` | `poetry run black ai_alert/ tests/` |
| `run-help` | `poetry run ai-alert --help` |
| `daemon-start` | `poetry run ai-alert daemon start --foreground` |
| `daemon-status` | `poetry run ai-alert status` |
| `daemon-logs` | `tail -f ~/.ai-alert/logs/daemon.out.log` |
| `clean` | Removes `__pycache__`, `*.pyc`, pytest/build caches |
| `setup-config` | Copies `configs/config.example.yaml` → `~/.ai-alert/config.yaml` if missing |
| `setup-env` | Prints the required `export` lines for tokens |
| `setup-all` | `setup-config` + `setup-env` |
| `version` | `poetry run ai-alert version` |

---

## Test Coverage

### CLI Tests (11 tests, `tests/test_cli.py`)

**`list` (3):**
- No alerts → "No alerts found." ✅
- Multiple alerts → all titles/IDs present in output ✅
- `--status pending` passed through to `store.list_alerts(status=...)` ✅

**`show` (3):**
- Nonexistent alert → exit code 1, "not found" ✅
- Alert without analysis → "No analysis yet" ✅
- Alert with analysis → root cause, suggested fix, files to inspect all present ✅

**`gc` (3):**
- No old alerts → "No alerts..." message, no deletes ✅
- `--dry-run` → "Would delete", `delete_alert` never called ✅
- Without `--dry-run` → "Deleted", `delete_alert` called once ✅

**`main` (2):**
- `--help` shows "AI Alert Agent" ✅
- `--version` shows version string ✅

All CLI tests use Click's `CliRunner` and mock `ai_alert.cli.Store` at the import site (context-manager mock via `__enter__`/`__exit__`), following the same external-boundary mocking approach used in every prior phase's test suite — no real SQLite file is touched.

**Total Phase 8:** 11 tests
**Cumulative (Phase 1-8):** 191 total tests (all passing ✅)

---

## Design Decisions

### Client-side filtering for `gc`

`Store` has no `WHERE received_at < ?` query, and Phase 8 is scoped to "implement exactly what's needed" — so `gc` pulls up to 10,000 alerts and filters in Python rather than adding a new `Store` method for a single call site. Acceptable at this project's scale (single-user, local SQLite); would need revisiting if the table grows past that limit.

### `--dry-run` is the default-safe path

Both `gc` and the earlier `analyze --dry-run` share the convention: destructive/costly operations require an explicit flag to actually execute, and the preview path never touches mutating store methods — verified directly in tests via `assert_not_called()` / `assert_called_once()`, not just by reading the output text.

### launchd over systemd

Dropped the plan's "optional systemd service template" — this is explicitly a MacBook-native tool (per `CLAUDE.md`/plan context: "runs locally on your MacBook"), and no Linux deployment target exists. Shipping a systemd unit for a target that doesn't exist would be exactly the kind of speculative, unused artifact this project's "no speculative abstractions" norm (carried over from the adjacent `cx-collector` Go project's conventions) argues against.

### Corrected pre-existing doc drift while touching README

While updating `README.md` for Phase 8, found and fixed several inaccuracies left over from earlier phases unrelated to this phase's new code:
- `ai-alert config check` (two words) doesn't exist — Click derives `config-check` (hyphenated) from the `config_check` function name. Fixed all three occurrences.
- `make dev-setup`, `make test-verbose`, `make type-check` were referenced but never existed in any Makefile version. Replaced with the real targets (`make dev`, `make setup-all`, plain `pytest -v`).
- `AI_ALERT_CLAUDE_MODEL` / `AI_ALERT_CLAUDE_EFFORT` / `AI_ALERT_LOG_LEVEL` env var overrides were documented but never implemented in `config.py` — verified via isolated interpreter test that setting them has no effect on the loaded `Config`. Replaced with an accurate description (edit the YAML directly; `--log-level` is a true per-command override).
- Left `GETTING_STARTED.md` as-is beyond one line — it's a Phase-1-era onboarding doc with its own "Next Phase: Phase 2" framing that was never part of the per-phase doc-update pattern (only `README.md` and `PHASE_N_CHECKLIST.md` get touched each phase); a full rewrite of it is out of scope for Phase 8.

---

## Verification

### Test Execution

```bash
# Disposable venv (system Python 3.9.6, mirrors Phases 5-7 methodology)
python3 -m venv .venv-phase8-test
source .venv-phase8-test/bin/activate
pip install --index-url https://pypi.org/simple pydantic pydantic-settings pyyaml \
  click loguru anthropic requests boto3 pytest pytest-mock pytest-asyncio pytest-cov responses

# Full suite
pytest tests/ -p no:cacheprovider -o addopts="" -q
# Result: 191 passed, 41 warnings (pydantic v2 ConfigDict deprecation, boto3/urllib3
# Python-3.9-EOL notices — pre-existing, unrelated to Phase 8 changes)

# Phase 8 only
pytest tests/test_cli.py -p no:cacheprovider -o addopts="" -v
# Result: 11 passed

# Cleanup
deactivate && rm -rf .venv-phase8-test
```

### Test Environment

- Python 3.9.6 (temporary venv, deleted after use)
- No real Slack/Sentry/AWS/Claude network calls — `Store` fully mocked at the CLI import boundary
- `click.testing.CliRunner` drives commands in-process; exit codes and stdout asserted directly

---

## Known Limitations

1. **`gc` scan cap** — loads up to 10,000 alerts to filter client-side; no pagination beyond that.
2. **No `systemd` template** — macOS-only tool, scoped out per plan.
3. **Background (non-foreground) daemon mode in the CLI itself is still a stub** — `ai-alert daemon start` without `--foreground` prints "not yet implemented" and exits 1; `launchd` is the supported way to run it unattended, by always invoking `--foreground` as the launchd job's own process.
4. **`GETTING_STARTED.md` not updated** — still reflects Phase 1 state (`make dev-setup`, missing `list`/`show`/`gc` in its command list beyond the one line fixed). Flagged above as an intentional scope boundary, not an oversight.

---

## Conclusion

✅ **Phase 8 Complete: Polish & Operations Implemented**

The agent now has full lifecycle CLI management (`list`, `show`, `gc` alongside the existing `analyze`, `status`, `config-check`, `version`, `daemon`), a macOS `launchd` template for unattended background operation, a working `Makefile` aligned to the real command surface, and corrected setup documentation.

All 8 phases of the original plan are now complete: Scaffold → Storage → Sentry → Claude → Codebase → CloudWatch → Slack Daemon → Polish & Ops.

**STATUS: ✅ ALL 8 PHASES COMPLETE — 191/191 TESTS PASSING**

---

**Implemented:** October 30, 2026
**Tests:** 191/191 passing ✅
**Status:** PROJECT COMPLETE (per original 8-phase plan)
