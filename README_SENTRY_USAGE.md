# AI Alert Agent — Sentry Issue Analysis with Claude

Automated Sentry alert triage powered by Claude AI. Analyzes error patterns, identifies root causes, and recommends fixes for cx-collector production issues.

---

## Quick Start

### 1. Analyze a Sentry Issue (Most Common)

```bash
cd /Users/ishan.shah/projects/ai-alert

# Analyze a specific issue
./ai-alert-ssl analyze 7691078133

# Force re-analyze even if already done
./ai-alert-ssl analyze 7691078133 --force

# Dry-run: show evidence and Claude prompt, don't call API
./ai-alert-ssl analyze 7691078133 --dry-run
```

**Output:**
```
✅ Analysis complete!

Root Cause Analysis:
================================================================================
Summary: Organization parameter missing when calling CMS GetCredentialResourceMetadataByOrganizationID API

Confidence: high
Error Category: api_error
Affected Component: cms-credentials-collector

Suggested Fix:
Ensure the organization ID is properly passed to GetCredentialResourceMetadataByOrganizationID

Files to Inspect:
  • internal/collector/cms/credentials.go
  • internal/clients/cms/cms.go

Follow-up Actions:
  • Review the CMS client initialization code
  • Check if organization parameter is required
  • Add validation for organization ID before calling CMS API

Tokens Used: 1450
Model: bedrock-claude-5-0-sonnet
```

---

## Setup Requirements

### Prerequisites

- **Python 3.11+** installed (check: `python3 --version`)
- **Poetry** installed (check: `poetry --version`)
- **SSL certificates** for corporate proxy (auto-handled by `ai-alert-ssl` wrapper)

### 1. Install Dependencies

```bash
cd /Users/ishan.shah/projects/ai-alert
poetry install
```

### 2. Environment Variables

Create or verify `.env` file in the project root:

```bash
# Sentry
SENTRY_API_TOKEN=sntrys_...                    # Get from: https://sentry.io/settings/account/api/auth-tokens/
SENTRY_ORGANIZATION=arcticwolf                 # Your Sentry org slug

# Anthropic/Claude
ANTHROPIC_API_KEY=sk-...                       # Your API key

# Slack (optional, for daemon mode)
SLACK_BOT_TOKEN=xoxb-...                       # From Slack app OAuth & Permissions
SLACK_APP_TOKEN=xapp-...                       # From Slack app Socket Mode

# AWS (optional, for CloudWatch logs)
AWS_PROFILE=default                            # Or use AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY
```

**Location:** `/Users/ishan.shah/projects/ai-alert/.env` (already exists)

### 3. SSL Certificate Setup

The `ai-alert-ssl` wrapper automatically extracts and manages CA certificates. It includes:
- Sentry certificates (arcticwolf.sentry.io)
- Anthropic/Claude gateway certificates
- AWN internal gateway chain

**No manual setup needed** — just use:
```bash
./ai-alert-ssl analyze <issue-id>
```

---

## CLI Commands

### **Analyze a Sentry Issue** (Primary Use Case)

```bash
# Basic analysis
poetry run ai-alert analyze 7691078133

# With options
poetry run ai-alert analyze 7691078133 --force      # Force re-analyze
poetry run ai-alert analyze 7691078133 --dry-run    # Show prompt only
```

**What happens:**
1. Fetches issue metadata from your Sentry instance
2. Gathers evidence (stack trace, tags, breadcrumbs)
3. Sends to Claude for analysis
4. Saves recommendation to database
5. Pretty-prints result

---

### **List Stored Alerts**

```bash
# Show all alerts
poetry run ai-alert list

# Filter by status
poetry run ai-alert list --status pending          # Not yet analyzed
poetry run ai-alert list --status analyzed         # Completed
poetry run ai-alert list --status failed           # Analysis failed

# Limit results
poetry run ai-alert list --limit 20
```

**Output:**
```
📋 3 Alert(s):

✅ 270fdf65... | 7691078133
   Title: *fmt.wrapError: cms GetCredentialResourceMetadataByOrganizationID...
   Status: AlertStatus.ANALYZED | Received: 2026-10-30 19:11:09

⏳ a1b2c3d4... | 7691078134
   Title: Connection timeout to Jira API
   Status: AlertStatus.PENDING | Received: 2026-10-30 20:15:33

❌ x9y8z7w6... | 7691078135
   Title: JSON parse error in Slack response
   Status: AlertStatus.FAILED | Received: 2026-10-30 21:30:00
```

---

### **Show Full Analysis**

```bash
# Get alert ID from 'list' command, then show details
poetry run ai-alert show 270fdf65-739e-4bfd-82dc-e663cfd66a8f
```

**Output:**
```
📝 Alert: 270fdf65-739e-4bfd-82dc-e663cfd66a8f

Sentry Issue:  7691078133
Title:         *fmt.wrapError: cms GetCredentialResourceMetadataByOrganizationID...
Status:        analyzed
Received:      2026-10-30 19:11:09

Analysis Results:
─────────────────────────────────────────────────────────────────
Root Cause:
  Organization parameter missing when calling CMS API

Confidence: high
Category:   api_error
Component:  cms-credentials-collector

Suggested Fix:
  Ensure organization ID is properly passed to GetCredentialResourceMetadataByOrganizationID

Files to Inspect:
  • internal/collector/cms/credentials.go
  • internal/clients/cms/cms.go

Follow-up Actions:
  • Review CMS client initialization
  • Check organization parameter requirement
  • Add validation before API call

Tokens Used: 1450
Model:       bedrock-claude-5-0-sonnet
Created:     2026-10-30 19:11:09
```

---

### **Check Status**

```bash
poetry run ai-alert status
```

**Output:**
```
📊 AI Alert Agent Status

Database:  ~/.ai-alert/data.db
Size:      2.3 MB

Alert Counts:
  Pending:   5
  Analyzed:  156
  Failed:    3

Latest Analysis:
  Issue:     7691078133
  Created:   2 hours ago
  Model:     bedrock-claude-5-0-sonnet
```

---

### **Validate Configuration**

```bash
poetry run ai-alert config-check
```

Shows resolved config (secrets redacted), validation errors if any.

---

### **Garbage Collection**

```bash
# Delete old alerts (default: older than 90 days)
poetry run ai-alert gc

# Delete alerts older than 30 days
poetry run ai-alert gc --days 30
```

---

### **Daemon Mode** (Slack Integration)

```bash
# Start in foreground (development/testing)
poetry run ai-alert daemon start --foreground

# Start in background (production)
poetry run ai-alert daemon start

# Stop daemon
poetry run ai-alert daemon stop

# Check daemon status
poetry run ai-alert status
```

**How it works:**
1. Daemon listens to Slack channel (#rnd_cyberpunks_alarms) via Socket Mode
2. When a Sentry alert is posted, extracts issue ID
3. Automatically runs analysis
4. Posts recommendation as threaded reply

---

### **Display Version**

```bash
poetry run ai-alert version
```

---

## Configuration File (Optional)

**Location:** `~/.ai-alert/config.yaml`

**Example:**
```yaml
sentry:
  organization: arcticwolf
  project: cx-collector

cloudwatch:
  enabled: true
  logGroupPrefix: /eks/cx-collector
  region: us-west-2
  lookbackMinutes: 5

codebase:
  repoPath: /Users/ishan.shah/projects/cx-collector

claude:
  model: bedrock-claude-5-0-sonnet    # For internal gateway
  effort: medium                      # low, medium, or high
  maxTokens: 8000

storage:
  dbPath: ~/.ai-alert/data.db

logging:
  dir: ~/.ai-alert/logs
  level: info                         # debug, info, warning, error

slack:
  channel: rnd_cyberpunks_alarms
  postReply: true

daemon:
  slackPostReply: true
```

Override config values via environment variables:
```bash
export AI_ALERT_CLAUDE_MODEL=claude-opus-5-5
export AI_ALERT_LOG_LEVEL=debug
poetry run ai-alert analyze 7691078133
```

---

## Data Storage

All analyses are persisted to **SQLite database** at `~/.ai-alert/data.db`

### Schema

**alerts table:**
```
id                 : UUID (unique per Sentry issue)
sentry_issue_id    : String (primary key for dedup)
sentry_url         : String
title              : String (error message)
slack_channel      : String
slack_message_ts   : String (for threaded replies)
status             : String (pending, analyzing, analyzed, failed)
received_at        : Timestamp
last_error         : String (if failed)
```

**analyses table:**
```
id                 : UUID
alert_id           : UUID (foreign key)
sentry_issue_id    : String
model              : String (bedrock-claude-5-0-sonnet, etc.)
root_cause         : String
confidence         : String (low, medium, high)
error_category     : String (api_error, parse_error, etc.)
affected_component : String (collector name)
recommendation_json: JSON (structured recommendation)
tokens_used        : Integer
created_at         : Timestamp
```

### Querying the Database

```bash
# List all analyses
sqlite3 ~/.ai-alert/data.db "SELECT sentry_issue_id, root_cause, confidence FROM analyses LIMIT 10;"

# Export to JSON
sqlite3 ~/.ai-alert/data.db ".mode json" "SELECT * FROM analyses;" > /tmp/analyses.json

# View full schema
sqlite3 ~/.ai-alert/data.db ".schema"

# Count by status
sqlite3 ~/.ai-alert/data.db "SELECT status, COUNT(*) FROM alerts GROUP BY status;"

# Find recent failures
sqlite3 ~/.ai-alert/data.db "SELECT sentry_issue_id, last_error, received_at FROM alerts WHERE status='failed' ORDER BY received_at DESC;"
```

---

## Real Examples

### Example 1: Batch Analysis

Analyze multiple Sentry issues:

```bash
for issue_id in 7691078133 7691078134 7691078135 7691078136; do
  echo "📌 Analyzing issue $issue_id..."
  ./ai-alert-ssl analyze $issue_id
  echo ""
done
```

### Example 2: Find and Analyze High-Frequency Issues

```bash
# Query Sentry directly (if you have jq installed)
ISSUE_IDS=$(curl -s \
  -H "Authorization: Bearer $SENTRY_API_TOKEN" \
  "https://arcticwolf.sentry.io/api/0/organizations/arcticwolf/issues/?sort=-lastSeen&limit=5" \
  | jq -r '.[] | .id')

for issue_id in $ISSUE_IDS; do
  echo "Analyzing $issue_id..."
  ./ai-alert-ssl analyze $issue_id
done
```

### Example 3: Check Analysis Results

```bash
# List all analyzed alerts
poetry run ai-alert list --status analyzed

# Show the most recent one
ALERT_ID=$(poetry run ai-alert list --status analyzed --limit 1 | grep "✅" | awk '{print $2}' | tr -d '...')
poetry run ai-alert show "$ALERT_ID"
```

### Example 4: Export Analysis Report

```bash
# Export all analyses as JSON
sqlite3 ~/.ai-alert/data.db ".mode json" << 'SQL' > /tmp/sentry-analyses.json
SELECT 
  a.sentry_issue_id,
  a.root_cause,
  a.confidence,
  a.affected_component,
  a.created_at,
  json_extract(a.recommendation_json, '$.suggested_fix') as suggested_fix
FROM analyses a
ORDER BY a.created_at DESC;
SQL

cat /tmp/sentry-analyses.json
```

### Example 5: Dry-Run with Prompt Inspection

```bash
# See exactly what Claude will receive
./ai-alert-ssl analyze 7691078133 --dry-run

# This shows:
# - Error title and metadata
# - Stack trace context
# - Code snippets from cx-collector
# - CloudWatch logs (if available)
# - The full prompt that would go to Claude
# - Skips the actual Claude API call
```

---

## Integration with Your Workflow

### Option 1: Manual Analysis (One-Off)
```bash
# Run when you see a Sentry alert
./ai-alert-ssl analyze 7691078133
```

### Option 2: Daemon Mode (Real-Time)
```bash
# Terminal 1: Start daemon in foreground
cd /Users/ishan.shah/projects/ai-alert
poetry run ai-alert daemon start --foreground

# Now when alerts post to Slack, daemon auto-analyzes and replies
```

### Option 3: Scheduled Batch (Cron/Launchd)
```bash
# Edit crontab
crontab -e

# Add: Run every 30 minutes to analyze pending alerts
*/30 * * * * cd /Users/ishan.shah/projects/ai-alert && ./ai-alert-ssl analyze $(sqlite3 ~/.ai-alert/data.db "SELECT sentry_issue_id FROM alerts WHERE status='pending' LIMIT 1;")
```

### Option 4: macOS Background Service (Launchd)

Create `~/Library/LaunchAgents/com.ai-alert.daemon.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ai-alert.daemon</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>cd /Users/ishan.shah/projects/ai-alert && poetry run ai-alert daemon start</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/ishan.shah/.ai-alert/logs/daemon.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/ishan.shah/.ai-alert/logs/daemon-error.log</string>
</dict>
</plist>
```

Then:
```bash
# Load daemon
launchctl load ~/Library/LaunchAgents/com.ai-alert.daemon.plist

# Check status
launchctl list | grep ai-alert

# Stop daemon
launchctl unload ~/Library/LaunchAgents/com.ai-alert.daemon.plist
```

---

## Troubleshooting

### SSL Certificate Error

**Error:**
```
ssl.SSLCertVerificationError: certificate verify failed: self-signed certificate in certificate chain
```

**Solution:** Use the wrapper script which auto-manages certificates:
```bash
./ai-alert-ssl analyze 7691078133
```

Or manually set CA bundle:
```bash
export REQUESTS_CA_BUNDLE=/path/to/ca-bundle.pem
poetry run ai-alert analyze 7691078133
```

---

### Model Not Allowed (403)

**Error:**
```
403 team_model_access_denied: This team can only access models=[bedrock-claude-5-0-sonnet, ...]
```

**Cause:** Internal gateway only allows specific model IDs.

**Solution:** Already fixed in code. Model names are auto-translated:
- `claude-sonnet-5-5` → `bedrock-claude-5-0-sonnet`
- `claude-opus-5-5` → `bedrock-claude-4-8-opus`
- `claude-haiku-5-5` → `bedrock-claude-5-5-haiku`

---

### Connection Timeout to Sentry

**Error:**
```
requests.exceptions.ConnectionError: Connection refused
```

**Solutions:**
1. Check Sentry token is valid: `echo $SENTRY_API_TOKEN`
2. Verify Sentry domain is reachable: `curl -I https://arcticwolf.sentry.io`
3. Check firewall/proxy settings
4. Try with CA bundle: `./ai-alert-ssl analyze 7691078133`

---

### Database Locked / Corrupt

**Error:**
```
sqlite3.OperationalError: database is locked
```

**Solution:**
```bash
# Backup old database
cp ~/.ai-alert/data.db ~/.ai-alert/data.db.backup

# Delete and recreate
rm ~/.ai-alert/data.db
poetry run ai-alert analyze 7691078133
```

---

### Check Logs

```bash
# View live logs
tail -f ~/.ai-alert/logs/ai-alert-*.log

# Enable debug logging
export AI_ALERT_LOG_LEVEL=debug
poetry run ai-alert analyze 7691078133

# Search logs for errors
grep -i error ~/.ai-alert/logs/ai-alert-*.log
```

---

### Sentry API Token Validation

```bash
# Test your token
export SENTRY_API_TOKEN="sntrys_..."
curl -i -H "Authorization: Bearer $SENTRY_API_TOKEN" \
  https://arcticwolf.sentry.io/api/0/organizations/arcticwolf/issues/?limit=1

# Should return 200 OK and JSON list
```

---

## Architecture

```
┌────────────────────────────────────────┐
│     Sentry (Your Instance)              │
│  arcticwolf.sentry.io                   │
│  - 223K+ errors from cx-collector       │
└────────────────────────────────────────┘
                    ↓ (REST API)
┌────────────────────────────────────────┐
│     AI Alert Agent                      │
│  - Fetches issue metadata               │
│  - Gathers evidence (code, logs)        │
│  - Sends to Claude                      │
│  - Stores analysis in SQLite            │
└────────────────────────────────────────┘
                    ↓
┌────────────────────────────────────────┐
│     Claude AI (Internal Gateway)        │
│  https://llm-gateway.us002-dev.rtkwlf.io
│  - Analyzes error patterns              │
│  - Identifies root cause                │
│  - Recommends fixes                     │
└────────────────────────────────────────┘
                    ↓
┌────────────────────────────────────────┐
│     Results                             │
│  ~/.ai-alert/data.db (SQLite)           │
│  - Alert records                        │
│  - Analysis recommendations             │
│  - Full chat history                    │
└────────────────────────────────────────┘
                    ↓
┌────────────────────────────────────────┐
│     Slack (Optional)                    │
│  #rnd_cyberpunks_alarms                 │
│  - Bot posts threaded replies           │
└────────────────────────────────────────┘
```

---

## FAQ

**Q: How do I find a Sentry issue ID?**
A: In Sentry, go to the issue page. The URL is `https://sentry.io/organizations/arcticwolf/issues/7691078133/` — the number is the ID.

**Q: Can I analyze issues from other Sentry organizations?**
A: Yes! Update `SENTRY_ORGANIZATION` in `.env` and ensure your `SENTRY_API_TOKEN` has access to that org.

**Q: How much does Claude analysis cost?**
A: Typical analysis uses 1000-2000 tokens. Check your Anthropic account for pricing.

**Q: Can I use the public Claude API instead of the internal gateway?**
A: Yes! Just don't set `ANTHROPIC_BASE_URL` in `.env` or settings.json. The agent will use `api.anthropic.com` by default.

**Q: How do I analyze all pending alerts at once?**
A: Not yet automated, but you can batch:
```bash
poetry run ai-alert list --status pending | grep "⏳" | awk '{print $3}' | while read id; do ./ai-alert-ssl analyze $id; done
```

**Q: Where are logs stored?**
A: `~/.ai-alert/logs/ai-alert-YYYY-MM-DD.log`

---

## Next Steps

1. **Try your first analysis:**
   ```bash
   ./ai-alert-ssl analyze 7691078133
   ```

2. **List your results:**
   ```bash
   poetry run ai-alert list --status analyzed
   ```

3. **Enable daemon mode** for Slack integration:
   ```bash
   poetry run ai-alert daemon start --foreground
   ```

4. **Set up launchd** for always-on background service (see Launchd section above)

---

## Support

For issues or questions:
- Check logs: `~/.ai-alert/logs/`
- Run config check: `poetry run ai-alert config-check`
- Verify Sentry token: `curl -i -H "Authorization: Bearer $SENTRY_API_TOKEN" https://arcticwolf.sentry.io/api/0/organizations/arcticwolf/issues/?limit=1`
- Review CLAUDE.md in cx-collector for architecture context
