# Alert Analyzer Agent — Setup & Execution Guide

## Overview

**Alert Analyzer Agent** is a standalone Python application that:
1. Receives Prometheus metric alerts from Slack channels
2. Analyzes root cause using Claude AI
3. Fetches CloudWatch logs for additional context (optional)
4. Correlates with cx-collector codebase (if enabled)
5. Posts analysis results back to Slack as threaded replies

The agent can run as:
- **CLI mode**: Analyze single alerts manually
- **Daemon mode**: Listen to Slack and auto-analyze alerts in real-time

---

## Prerequisites

### 1. System Requirements

- **Python:** 3.11 or later
  ```bash
  python3 --version  # Should be 3.11+
  ```

- **Poetry:** For dependency management
  ```bash
  # Install if not already installed
  curl -sSL https://install.python-poetry.org | python3 -
  export PATH="$HOME/.local/bin:$PATH"
  poetry --version
  ```

### 2. API Credentials & Tokens

Before running the agent, gather these credentials:

#### a) Anthropic API Key (Required for Claude analysis)
- Get from: https://console.anthropic.com/account/keys
- Set as environment variable:
  ```bash
  export ANTHROPIC_API_KEY="sk-ant-..."
  ```

#### b) Sentry API Token (Required for Sentry alerts)
- Go to: https://sentry.io/settings/account/api/auth-tokens/
- Create token with scopes: `event:read`, `org:read`, `project:read`
- Set environment variable:
  ```bash
  export SENTRY_API_TOKEN="sntrys_..."
  ```

#### c) Slack Tokens (Required for daemon mode)

**For Socket Mode (recommended for local MacBook):**

1. Go to: https://api.slack.com/apps
2. Create a new app → "From scratch"
   - App Name: `alert-analyzer`
   - Workspace: select your workspace
3. Enable **Socket Mode** (left sidebar)
   - Toggle on, generate token (starts with `xapp-`)
   - Save as: `SLACK_APP_TOKEN=xapp-...`
4. Add **OAuth Scopes** (left sidebar → OAuth & Permissions):
   - `channels:history` (read messages)
   - `chat:write` (post messages)
   - `app_mentions:read` (optional)
5. **Install to Workspace** → authorize
   - Copy Bot User OAuth Token (starts with `xoxb-`)
   - Save as: `SLACK_BOT_TOKEN=xoxb-...`
6. **Event Subscriptions** (left sidebar):
   - Enable Events
   - Subscribe to: `message.channels`
   - Save
7. Invite bot to channel:
   ```bash
   # In Slack channel #rnd_cyberpunks_alarms
   /invite @alert-analyzer
   ```

#### d) AWS Credentials (Optional for CloudWatch logs)

If CloudWatch integration is enabled:
```bash
# Verify AWS CLI access
aws sts get-caller-identity

# If not configured, set env vars:
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_SESSION_TOKEN="..."  # if using temporary credentials
```

#### e) cx-collector Repository Path (Optional)

For code context analysis:
```bash
export CODEBASE_REPO_PATH="/Users/ishan.shah/projects/cx-collector"
```

### 3. Environment File

Create `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` and fill in:
```bash
# Claude API
ANTHROPIC_API_KEY=sk-ant-...

# Sentry
SENTRY_API_TOKEN=sntrys_...
SENTRY_ORGANIZATION=arcticwolf

# Slack (for daemon mode)
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
SLACK_CHANNEL=rnd_cyberpunks_alarms

# AWS (optional)
AWS_REGION=us-west-2

# cx-collector (optional)
CODEBASE_REPO_PATH=/Users/ishan.shah/projects/cx-collector

# Logging
LOG_LEVEL=info
```

---

## Installation

### Step 1: Install Dependencies

```bash
cd /Users/ishan.shah/projects/ai-alert

# Install all Python dependencies via Poetry
poetry install

# Verify installation
poetry run ai-alert --version
```

### Step 2: Verify Configuration

```bash
# Load environment variables
source .env

# Check configuration
poetry run ai-alert config check
```

Should output:
```
✅ Configuration validated
Claude Model: claude-sonnet-5-5
Sentry Organization: arcticwolf
Slack Channel: rnd_cyberpunks_alarms
Database: ~/.ai-alert/data.db
```

### Step 3: Test Basic CLI

```bash
# Analyze a test Sentry issue
poetry run ai-alert analyze 7691078133 --dry-run

# Should output evidence gathered (no Claude API call with --dry-run)
```

---

## Execution Modes

### Mode 1: CLI — Analyze Single Alert

```bash
# Basic analysis
poetry run ai-alert analyze <sentry-issue-id>

# Dry-run (gather evidence, print prompt, no API call)
poetry run ai-alert analyze <sentry-issue-id> --dry-run

# Force re-analysis (ignore duplicate check)
poetry run ai-alert analyze <sentry-issue-id> --force

# Example
poetry run ai-alert analyze 7691078133
```

**Output:**
- Prints formatted analysis to console
- Saves to SQLite: `~/.ai-alert/data.db`
- Returns exit code 0 on success

### Mode 2: Daemon — Listen to Slack in Real-Time

```bash
# Start daemon in foreground (logs to stdout)
poetry run ai-alert daemon start --foreground

# In another terminal, verify it's running
poetry run ai-alert status

# Stop daemon
Ctrl-C (foreground) or:
poetry run ai-alert daemon stop
```

**Behavior:**
- Daemon starts Socket Mode listener
- Listens to Slack channel: `#rnd_cyberpunks_alarms`
- On new message: extracts alert ID, auto-analyzes, posts result as threaded reply
- Graceful shutdown on SIGINT (Ctrl-C)

**Background Execution (macOS):**

For persistent background operation, use launchd:

```bash
# Load the daemon
launchctl load configs/com.alert-analyzer.daemon.plist

# View logs
log show --predicate 'process == "alert-analyzer"' --last 1h

# Stop the daemon
launchctl stop com.alert-analyzer.daemon

# Unload (disable autostart)
launchctl unload configs/com.alert-analyzer.daemon.plist
```

### Mode 3: CLI — Database Queries

```bash
# List all alerts
poetry run ai-alert list

# List by status
poetry run ai-alert list --status pending
poetry run ai-alert list --status analyzed

# Show detailed analysis
poetry run ai-alert show <alert-id>

# Database statistics
poetry run ai-alert status
```

### Mode 4: Manual Database Inspection

```bash
# Connect to SQLite
sqlite3 ~/.ai-alert/data.db

# List tables
.tables

# View all analyses (JSON format)
.mode json
SELECT * FROM analyses LIMIT 5;

# Query by status
SELECT sentry_issue_id, status, created_at FROM alerts WHERE status = 'analyzed';

# Export results
.mode csv
.output /tmp/analyses.csv
SELECT * FROM analyses;
.quit
```

---

## Quick Start (TL;DR)

```bash
# 1. Set up credentials
export ANTHROPIC_API_KEY="sk-ant-..."
export SENTRY_API_TOKEN="sntrys_..."
export SLACK_BOT_TOKEN="xoxb-..."
export SLACK_APP_TOKEN="xapp-..."

# 2. Install
cd /Users/ishan.shah/projects/ai-alert
poetry install

# 3. Verify config
poetry run ai-alert config check

# 4. Test CLI
poetry run ai-alert analyze 7691078133 --dry-run

# 5. Run full analysis
poetry run ai-alert analyze 7691078133

# 6. Check database
poetry run ai-alert list

# 7. Start daemon (optional)
poetry run ai-alert daemon start --foreground
```

---

## Common Tasks

### Analyze Multiple Alerts

```bash
for issue_id in 7691078133 7691078134 7691078135; do
  poetry run ai-alert analyze $issue_id
done
```

### Export All Analyses

```bash
# JSON export
sqlite3 ~/.ai-alert/data.db ".mode json" "SELECT * FROM analyses;" > /tmp/analyses.json

# CSV export
sqlite3 ~/.ai-alert/data.db ".mode csv" "SELECT * FROM analyses;" > /tmp/analyses.csv
```

### View Logs

```bash
# Real-time logs (follow)
tail -f ~/.ai-alert/logs/ai-alert-*.log

# Search logs for errors
grep "ERROR" ~/.ai-alert/logs/ai-alert-*.log

# View last 50 lines
tail -50 ~/.ai-alert/logs/ai-alert-$(date +%Y-%m-%d).log
```

### Reset Database

```bash
# WARNING: This deletes all stored analyses
rm ~/.ai-alert/data.db

# Next run will recreate schema
poetry run ai-alert analyze <id>
```

---

## Troubleshooting

### Issue: `403 team_model_access_denied`

**Cause:** Model name not recognized by internal Claude gateway

**Solution:**
```bash
# Check ANTHROPIC_BASE_URL and model name
poetry run ai-alert config check

# If using internal gateway, ensure model is in this list:
# - bedrock-claude-5-0-sonnet
# - bedrock-claude-4-8-opus
# - bedrock-claude-5-5-haiku
```

### Issue: `SSL: CERTIFICATE_VERIFY_FAILED`

**Cause:** Corporate proxy or internal certificate chain not trusted

**Solution:**
```bash
# Option 1: Use the wrapper script (auto-discovers certs)
./ai-alert-ssl analyze <id>

# Option 2: Set custom CA bundle
export SSL_CERT_FILE="/path/to/ca-bundle.pem"
poetry run ai-alert analyze <id>
```

### Issue: Slack daemon not receiving messages

**Cause:** Bot not invited to channel, or Socket Mode not enabled

**Solution:**
```bash
# 1. Verify Socket Mode enabled
poetry run ai-alert config check | grep -i slack

# 2. Invite bot to channel (in Slack)
/invite @alert-analyzer

# 3. Check logs
tail -f ~/.ai-alert/logs/ai-alert-*.log | grep -i slack

# 4. Restart daemon
Ctrl-C
poetry run ai-alert daemon start --foreground
```

### Issue: `SENTRY_API_TOKEN not set or invalid`

**Cause:** Token missing or expired

**Solution:**
```bash
# Verify token
curl -H "Authorization: Bearer $SENTRY_API_TOKEN" \
  https://sentry.io/api/0/organizations/arcticwolf/issues/?limit=1

# If 401/403, regenerate token at:
# https://sentry.io/settings/account/api/auth-tokens/

# Update .env with new token
export SENTRY_API_TOKEN="sntrys_..."
```

### Issue: `Database is locked`

**Cause:** Multiple processes accessing SQLite simultaneously

**Solution:**
```bash
# Stop all instances
poetry run ai-alert daemon stop
pkill -f "ai-alert"

# Wait a moment
sleep 2

# Restart
poetry run ai-alert daemon start --foreground
```

---

## Architecture & Files

### Project Structure

```
alert-analyzer-agent/
├── ai_alert/                          # Main Python package
│   ├── __init__.py
│   ├── __main__.py                    # Entry point
│   ├── cli.py                         # CLI commands
│   ├── config.py                      # Configuration loader
│   ├── models.py                      # Pydantic data models
│   ├── store.py                       # SQLite persistence
│   ├── logger.py                      # Logging setup
│   └── services/
│       ├── analyzer.py                # Main orchestrator
│       ├── sentry_fetcher.py          # Sentry API client
│       ├── claude_client.py           # Claude API wrapper
│       ├── cloudwatch_fetcher.py      # AWS CloudWatch client
│       ├── codebase_analyzer.py       # cx-collector code reader
│       ├── slack_listener.py          # Slack Socket Mode listener
│       └── slack_poster.py            # Slack message poster
├── tests/                             # Unit tests
├── configs/                           # Configuration templates
├── fixtures/                          # Test fixtures
├── pyproject.toml                     # Poetry dependencies
├── poetry.lock                        # Locked dependency versions
├── .env.example                       # Environment variables template
├── README.md                          # Project overview
├── README_SENTRY_USAGE.md             # Detailed usage guide
├── SETUP.md                           # This file
├── QUICK_REFERENCE.md                 # Command cheat sheet
└── ai-alert-ssl                       # SSL/CA cert wrapper script
```

### Key Components

| Component | Purpose |
|-----------|---------|
| **cli.py** | Click-based CLI entry point (analyze, daemon, list, show) |
| **analyzer.py** | Orchestrates evidence gathering → Claude → DB persistence |
| **sentry_fetcher.py** | REST API client for Sentry issues |
| **claude_client.py** | Anthropic SDK wrapper with model-name translation |
| **cloudwatch_fetcher.py** | AWS SDK for CloudWatch Logs Insights |
| **slack_listener.py** | Socket Mode listener for real-time Slack messages |
| **slack_poster.py** | Posts formatted results back to Slack |
| **store.py** | SQLite CRUD operations for alerts/analyses |

---

## Integration with cx-collector

The agent uses the **local cx-collector clone** for code context (if `CODEBASE_REPO_PATH` is set).

### What It Does

1. **Stack Frame Analysis:** When a Sentry event includes file:line, reads the file from local cx-collector clone
2. **Component Identification:** Extracts component names from error messages, uses `git grep` to find related files
3. **Context**: Sends relevant code snippets to Claude for root-cause analysis

### What It Does NOT Do

- Does NOT modify cx-collector code
- Does NOT run cx-collector's build/tests
- Does NOT require cx-collector to be running
- Uses local clone as **read-only reference material**

### Configuration

```bash
# Optional: Path to local cx-collector clone
export CODEBASE_REPO_PATH="/Users/ishan.shah/projects/cx-collector"

# If not set, agent still works (just without code context)
```

---

## Configuration Reference

### Config File: `~/.ai-alert/config.yaml`

```yaml
slack:
  channel: rnd_cyberpunks_alarms      # Slack channel to monitor
  enabled: true

sentry:
  organization: arcticwolf            # Sentry organization
  api_token: ${SENTRY_API_TOKEN}      # From env var

claude:
  model: claude-sonnet-5-5            # AI model
  effort: medium                      # Analysis depth
  max_tokens: 8000                    # Max response length

cloudwatch:
  enabled: true                       # Fetch pod logs
  log_group_prefix: /eks/cx-collector
  region: us-west-2
  lookback_minutes: 5

codebase:
  repo_path: ${CODEBASE_REPO_PATH}    # Local cx-collector clone

daemon:
  slack_post_reply: true              # Post results to Slack
  graceful_shutdown_timeout: 30

storage:
  db_path: ~/.ai-alert/data.db        # SQLite database

logging:
  dir: ~/.ai-alert/logs
  level: info                         # debug, info, warning, error
```

---

## Testing

```bash
# Run all tests
poetry run pytest -v

# Run specific test file
poetry run pytest tests/test_analyzer.py -v

# Run with coverage
poetry run pytest --cov=ai_alert tests/

# Skip slow tests
poetry run pytest -m "not slow"
```

---

## Support & Documentation

- **README.md** — Project overview and architecture
- **README_SENTRY_USAGE.md** — Detailed guide for Sentry analysis
- **QUICK_REFERENCE.md** — Command cheat sheet
- **DOCS_INDEX.md** — Navigation hub for all documentation

---

## Next Steps

1. ✅ Install dependencies: `poetry install`
2. ✅ Configure credentials in `.env`
3. ✅ Verify setup: `poetry run ai-alert config check`
4. ✅ Test CLI: `poetry run ai-alert analyze <id> --dry-run`
5. ✅ Run full analysis: `poetry run ai-alert analyze <id>`
6. ✅ Start daemon (optional): `poetry run ai-alert daemon start --foreground`

---

**Last Updated:** November 4, 2026  
**Project:** Alert Analyzer Agent  
**Repository:** https://github.com/IshanCSE/alert-analyzer-agent
