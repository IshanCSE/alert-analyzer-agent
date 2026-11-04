# AI Alert — Quick Reference Card

## Most Common Tasks

### Analyze a Single Issue
```bash
cd /Users/ishan.shah/projects/ai-alert
./ai-alert-ssl analyze 7691078133
```

### List All Analyses
```bash
poetry run ai-alert list
```

### Show Details of an Analysis
```bash
poetry run ai-alert show 270fdf65-739e-4bfd-82dc-e663cfd66a8f
```

### Check Status
```bash
poetry run ai-alert status
```

---

## One-Liner Reference

| Task | Command |
|------|---------|
| **Analyze issue** | `./ai-alert-ssl analyze 7691078133` |
| **Force re-analyze** | `./ai-alert-ssl analyze 7691078133 --force` |
| **Dry-run (no API call)** | `./ai-alert-ssl analyze 7691078133 --dry-run` |
| **List all** | `poetry run ai-alert list` |
| **List pending** | `poetry run ai-alert list --status pending` |
| **List analyzed** | `poetry run ai-alert list --status analyzed` |
| **Show analysis** | `poetry run ai-alert show <alert-id>` |
| **Check status** | `poetry run ai-alert status` |
| **Validate config** | `poetry run ai-alert config-check` |
| **Clean old data** | `poetry run ai-alert gc --days 30` |

---

## Database Queries

```bash
# Quick SQL to database
sqlite3 ~/.ai-alert/data.db "SELECT sentry_issue_id, root_cause FROM analyses LIMIT 5;"

# Export to JSON
sqlite3 ~/.ai-alert/data.db ".mode json" "SELECT * FROM analyses;" > /tmp/analyses.json

# Count analyses
sqlite3 ~/.ai-alert/data.db "SELECT COUNT(*) FROM analyses;"

# Find recent failures
sqlite3 ~/.ai-alert/data.db "SELECT sentry_issue_id, last_error FROM alerts WHERE status='failed' LIMIT 10;"
```

---

## Environment Setup

### 1. Verify Tokens
```bash
echo $SENTRY_API_TOKEN
echo $ANTHROPIC_API_KEY
```

### 2. Test Sentry Access
```bash
curl -s -H "Authorization: Bearer $SENTRY_API_TOKEN" \
  https://arcticwolf.sentry.io/api/0/organizations/arcticwolf/issues/?limit=1 | head -20
```

### 3. Check Logs
```bash
tail -f ~/.ai-alert/logs/ai-alert-*.log
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| SSL certificate error | Use `./ai-alert-ssl` wrapper |
| 403 team_model_access | Already fixed in code (auto-translates model names) |
| Connection timeout | Check: `curl https://arcticwolf.sentry.io` |
| Database locked | `rm ~/.ai-alert/data.db` and restart |
| Invalid token | Run `poetry run ai-alert config-check` |

---

## Data Storage

- **Database:** `~/.ai-alert/data.db` (SQLite)
- **Logs:** `~/.ai-alert/logs/ai-alert-*.log`
- **Config:** `~/.ai-alert/config.yaml`

---

## For Full Details

See: [README_SENTRY_USAGE.md](README_SENTRY_USAGE.md)
