# AI Alert Agent 🤖

An AI-powered Sentry alert triage agent that analyzes errors with Claude, runs locally on your MacBook.

> 📖 **For detailed usage instructions and examples, see [README_SENTRY_USAGE.md](README_SENTRY_USAGE.md)**

## Features

- 🎯 **Auto-Analysis**: Receive Slack alerts → analyze with Claude → post results as threads
- 📊 **Evidence Gathering**: Fetches Sentry events, CloudWatch logs, and local codebase context
- 💾 **Local-First**: SQLite persistence, no external database needed
- 🔧 **CLI & Daemon**: Manual analysis or continuous background listening
- ⚡ **Fast Iteration**: Direct Python orchestration, minimal framework overhead

## Quick Start

### Prerequisites

- Python 3.11+
- Poetry (dependency manager)
- Slack bot + app tokens (Socket Mode)
- Sentry API token
- Anthropic API key

### Setup

```bash
# Clone or create the project
cd /Users/ishan.shah/projects/ai-alert

# Install dependencies (production + dev)
make dev

# Scaffold config + show required env vars
make setup-all

# This creates:
# - ~/.ai-alert/config.yaml (copied from configs/config.example.yaml)
# - ~/.ai-alert/logs/ (log directory, created on first run)
```

### Configure

1. **Set required tokens** (shell profile or `.env`, see `.env.example`):
   ```bash
   export SLACK_BOT_TOKEN="xoxb-your-token"
   export SLACK_APP_TOKEN="xapp-your-token"
   export SENTRY_API_TOKEN="sntrys-your-token"
   export ANTHROPIC_API_KEY="sk-ant-your-key"
   ```

2. **Edit `~/.ai-alert/config.yaml`** to match your Slack channel, Sentry org/project, and codebase path.

3. **Verify configuration**:
   ```bash
   poetry run ai-alert config-check
   ```

### Test Installation

```bash
# Show version
make version

# Run all tests
make test

# Check code quality
make lint
```

## Usage

### CLI Commands

```bash
# Analyze a specific Sentry issue
poetry run ai-alert analyze <issue-id>

# Dry run (gather evidence, show prompt, don't call Claude)
poetry run ai-alert analyze <issue-id> --dry-run

# Force re-analysis of already-analyzed issue
poetry run ai-alert analyze <issue-id> --force

# Check status and database info
poetry run ai-alert status

# List alerts by status
poetry run ai-alert list --status pending
poetry run ai-alert list --status analyzed
poetry run ai-alert list --status all --limit 100

# Show full analysis for an alert
poetry run ai-alert show <alert-id>

# Garbage collect alerts older than N days (default 30)
poetry run ai-alert gc --days 30 --dry-run   # preview only
poetry run ai-alert gc --days 30             # actually delete

# Validate configuration
poetry run ai-alert config-check

# Show version
poetry run ai-alert version
```

### Daemon Mode (Background Listening)

```bash
# Start daemon in foreground (logs to console)
poetry run ai-alert daemon start --foreground
# or: make daemon-start

# Ctrl-C to stop gracefully
```

When the daemon is running:
1. Slack messages in `#rnd_cyberpunks_alarms` are automatically detected
2. Sentry issue ID is extracted
3. Analysis runs in the background
4. Results posted as threaded reply

#### Running persistently with launchd (macOS)

`configs/com.ai-alert.daemon.plist` is a template for running the daemon as a
background `launchd` service that survives terminal closes and restarts on
crash:

```bash
# 1. Copy and fill in real values (paths, tokens) — do not commit real tokens
cp configs/com.ai-alert.daemon.plist ~/Library/LaunchAgents/com.ai-alert.daemon.plist
nano ~/Library/LaunchAgents/com.ai-alert.daemon.plist

# 2. Load it
launchctl load ~/Library/LaunchAgents/com.ai-alert.daemon.plist

# 3. Check logs
make daemon-logs
# or: tail -f ~/.ai-alert/logs/daemon.out.log

# 4. Stop/unload
launchctl unload ~/Library/LaunchAgents/com.ai-alert.daemon.plist
```

Background mode via `ai-alert daemon start` (without `--foreground`) is not
implemented — use `--foreground` under `launchd`/`tmux`/`screen` instead.

## Development

### Project Structure

```
ai-alert/
├── ai_alert/              # Main package
│   ├── cli.py            # Click commands (analyze, status, list, show, gc, daemon)
│   ├── config.py         # Configuration management
│   ├── logger.py         # Logging setup
│   ├── models.py         # Pydantic data models
│   ├── store.py          # SQLite persistence (Phase 2)
│   └── services/         # External service integrations
│       ├── analyzer.py            # Main orchestrator (Phase 4)
│       ├── sentry_fetcher.py      # Sentry client (Phase 3)
│       ├── claude_client.py       # Claude API (Phase 4)
│       ├── codebase_analyzer.py   # Local repo code context (Phase 5)
│       ├── cloudwatch_fetcher.py  # CloudWatch log queries (Phase 6)
│       ├── slack_listener.py      # Socket Mode listener (Phase 7)
│       └── slack_poster.py        # Threaded Slack replies (Phase 7)
├── tests/                 # Unit tests (191 tests, Phases 1-8)
├── configs/                # launchd plist + example YAML config
│   ├── com.ai-alert.daemon.plist
│   └── config.example.yaml
├── fixtures/              # Config examples
├── .env.example           # Environment variable template
├── pyproject.toml        # Poetry dependencies
└── Makefile              # Development commands
```

### Development Workflow

```bash
# Format code
make format

# Lint
make lint

# Run tests
make test

# Clean build artifacts
make clean
```

## Implementation Phases

| Phase | Tasks | Status |
|-------|-------|--------|
| **1** | Scaffold, config, CLI | ✅ Complete |
| **2** | SQLite store, CRUD | ✅ Complete |
| **3** | Sentry fetcher | ✅ Complete |
| **4** | Claude integration | ✅ Complete |
| **5** | Codebase analysis | ✅ Complete |
| **6** | CloudWatch integration | ✅ Complete |
| **7** | Slack daemon (Socket Mode) | ✅ Complete |
| **8** | Polish + operations | ✅ Complete |

## Configuration

Default config location: `~/.ai-alert/config.yaml`

```yaml
slack:
  channel: rnd_cyberpunks_alarms

sentry:
  organization: arcticwolf
  project: cx-collector

claude:
  model: claude-sonnet-5-5  # or claude-opus-5-5
  effort: medium

storage:
  db_path: ~/.ai-alert/data.db

logging:
  dir: ~/.ai-alert/logs
  level: info
```

Required secrets (read directly from the environment, not the YAML file):
- `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN` — daemon mode (Socket Mode)
- `SENTRY_API_TOKEN` — Sentry REST API auth
- `ANTHROPIC_API_KEY` — Claude API auth

To change `claude.model`, `claude.effort`, or `logging.level`, edit
`~/.ai-alert/config.yaml` directly, or pass `--log-level` to any CLI command.

## Logging

Logs are written to `~/.ai-alert/logs/ai-alert-YYYY-MM-DD.log`

- Daily rotation at midnight
- 7-day retention
- Structured JSON output
- Console output during development

```bash
# View current day's logs
tail -f ~/.ai-alert/logs/ai-alert-$(date +%Y-%m-%d).log

# View all recent logs
ls -lh ~/.ai-alert/logs/
```

## Architecture

```
Slack (Socket Mode) → MessageParser → Analyzer
                                        ├─ Fetch Sentry
                                        ├─ Fetch CloudWatch
                                        ├─ Read codebase
                                        └─ Call Claude
                                        
                                     ↓ Store + Reply
                                     
                          SQLite ← Analysis
                                     ↓
                          Slack threaded reply
```

## Troubleshooting

### Tests failing

```bash
# make test already runs pytest -v; to isolate a file:
poetry run pytest tests/test_config.py -v
```

### Configuration issues

```bash
# Validate config and show resolved values
poetry run ai-alert config-check

# Check if required directories exist
ls -la ~/.ai-alert/
```

### Missing dependencies

```bash
# Reinstall all dependencies
poetry install --no-cache

# Update dependencies
poetry update
```

## Contributing

Development setup:
```bash
make dev
make setup-all
make test
```

Code quality checks before commit:
```bash
make format
make lint
```

## License

MIT

## Support

For issues or questions, refer to the plan at:
`/Users/ishan.shah/.claude/plans/we-get-alert-in-functional-squirrel.md`
