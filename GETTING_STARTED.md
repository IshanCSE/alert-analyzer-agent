# Getting Started with AI Alert Agent

## Prerequisites Checklist

Before proceeding, ensure you have:

- [ ] Python 3.11+ (`python3 --version`)
- [ ] Poetry (`poetry --version`)
- [ ] `SLACK_BOT_TOKEN` (xoxb-...)
- [ ] `SLACK_APP_TOKEN` (xapp-...)
- [ ] `SENTRY_API_TOKEN` (sntrys-...)
- [ ] `ANTHROPIC_API_KEY` (sk-ant-...)
- [ ] AWS credentials (optional, for CloudWatch)

## Installation Steps

### Step 1: Install Python 3.11+

Check current version:
```bash
python3 --version
```

If less than 3.11, install:
```bash
# Option A: Homebrew
brew install python@3.11

# Option B: pyenv
brew install pyenv
pyenv install 3.11.0
pyenv global 3.11.0

# Verify
python3 --version
```

### Step 2: Install Poetry

```bash
curl -sSL https://install.python-poetry.org | python3 -
export PATH="$HOME/.local/bin:$PATH"
poetry --version
```

Add to your shell profile (`~/.zshrc` or `~/.bash_profile`):
```bash
export PATH="$HOME/.local/bin:$PATH"
```

Then reload:
```bash
source ~/.zshrc  # or source ~/.bash_profile
```

### Step 3: Clone Project & Setup

```bash
cd /Users/ishan.shah/projects/ai-alert
make dev-setup
```

This will:
- Install dependencies in isolated environment
- Create `~/.ai-alert/` directory
- Copy `config.yaml` and `.env` templates

### Step 4: Configure

Edit environment variables:
```bash
nano ~/.ai-alert/.env
```

Fill in your tokens:
```
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_APP_TOKEN=xapp-your-app-token-here
SENTRY_API_TOKEN=sntrys-your-token-here
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

Edit configuration (optional):
```bash
nano ~/.ai-alert/config.yaml
```

### Step 5: Verify Installation

```bash
cd /Users/ishan.shah/projects/ai-alert

# Show version
poetry run ai-alert version

# Validate config
poetry run ai-alert config check

# Run tests
make test
```

All three should complete without errors! ✓

## First Commands to Try

```bash
# Show help
poetry run ai-alert --help

# Check daemon commands
poetry run ai-alert daemon --help

# Analyze a Sentry issue (dry-run, doesn't call Claude yet)
poetry run ai-alert analyze 12345 --dry-run

# Show status
poetry run ai-alert status
```

## Development Workflow

```bash
# Format code
make format

# Check code quality
make lint

# Run type checking
make type-check

# Run tests with coverage
make test-cov

# Clean build artifacts
make clean
```

## File Locations

```
Project:     /Users/ishan.shah/projects/ai-alert
Config:      ~/.ai-alert/config.yaml
Env vars:    ~/.ai-alert/.env
Database:    ~/.ai-alert/data.db
Logs:        ~/.ai-alert/logs/
```

## Troubleshooting

### Poetry not found
```bash
# Make sure it's in PATH
export PATH="$HOME/.local/bin:$PATH"
# Add to ~/.zshrc or ~/.bash_profile
```

### Python version issue
```bash
python3 --version  # Check version
which python3      # Check location
```

### Poetry dependency conflicts
```bash
poetry install --no-cache
poetry update
```

### Tests failing
```bash
# Run with verbose output
poetry run pytest -v

# Run specific test
poetry run pytest tests/test_config.py -v
```

### Config validation errors
```bash
poetry run ai-alert config check
ls -la ~/.ai-alert/
```

## What's Implemented

✅ **Phase 1: Scaffold & Config**
- CLI commands (analyze, daemon, status, version, config-check)
- Configuration management (YAML + env override)
- Logging setup with daily rotation
- Data models (Alert, Analysis, Recommendation)
- Test fixtures and examples
- Development tooling (Makefile, linting, formatting)

## Next Phase: Phase 2

**Phase 2: Local Storage (SQLite)** — Estimated 2-3 days

After Phase 1 is verified:
1. Implement `Store` class with SQLite
2. Create database schema (alerts, analyses)
3. Write CRUD operations
4. Add unit tests
5. Enable `ai-alert analyze` to persist data

---

## Need Help?

1. Check the plan: `/Users/ishan.shah/.claude/plans/we-get-alert-in-functional-squirrel.md`
2. Read the README: `./README.md`
3. Review Phase 1 checklist: `./PHASE_1_CHECKLIST.md`
4. Check test examples: `./tests/`

---

**Ready to begin? Run:**

```bash
cd /Users/ishan.shah/projects/ai-alert
make version
```

If this shows a version number, Phase 1 is working! 🎉
