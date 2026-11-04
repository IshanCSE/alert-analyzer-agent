# AI Alert Documentation Index

## 📖 Where to Start?

### **I want to analyze a Sentry issue right now**
→ Go to: [QUICK_REFERENCE.md](QUICK_REFERENCE.md) → "Most Common Tasks" section

### **I need complete setup instructions**
→ Go to: [README_SENTRY_USAGE.md](README_SENTRY_USAGE.md) → "Setup Requirements" section

### **I need to understand all available commands**
→ Go to: [README_SENTRY_USAGE.md](README_SENTRY_USAGE.md) → "CLI Commands" section

### **I'm getting an error**
→ Go to: [README_SENTRY_USAGE.md](README_SENTRY_USAGE.md) → "Troubleshooting" section

### **I want quick command reference**
→ Go to: [QUICK_REFERENCE.md](QUICK_REFERENCE.md)

---

## 📁 Documentation Structure

```
/Users/ishan.shah/projects/ai-alert/
├── README.md                       ← Start here for project overview
├── README_SENTRY_USAGE.md          ← COMPREHENSIVE guide (18 KB)
├── QUICK_REFERENCE.md              ← Command cheat sheet (2.5 KB)
├── DOCS_INDEX.md                   ← This file
├── ai-alert-ssl                    ← Wrapper script (use this!)
└── ai_alert/
    ├── services/
    │   ├── sentry_fetcher.py       ← Fetches from Sentry
    │   ├── claude_client.py         ← Calls Claude AI
    │   ├── analyzer.py              ← Orchestrator
    │   └── ...
    └── cli.py                       ← Command definitions
```

---

## 🚀 Quickest Start (Copy-Paste)

```bash
# 1. Navigate to project
cd /Users/ishan.shah/projects/ai-alert

# 2. Analyze a Sentry issue
./ai-alert-ssl analyze 7691078133

# 3. List your analyses
poetry run ai-alert list

# 4. Show full details
poetry run ai-alert show <alert-id>
```

---

## 📋 File-by-File Guide

### **README.md** (Main README)
- Project description
- Feature overview
- Development structure
- Phases completed
- **Start here** for architecture understanding

### **README_SENTRY_USAGE.md** (Complete Manual) ⭐ PRIMARY REFERENCE
- Quick start with 3 commands
- Setup requirements (env vars, certs)
- **All CLI commands** (analyze, list, show, status, config-check, daemon, gc, version)
- Configuration options
- **Database queries** (how to access stored analyses)
- **Real examples** (batch analysis, dry-run, exports, daemon setup)
- **Integration options** (manual, daemon, cron, launchd)
- **Troubleshooting** (SSL errors, model errors, timeouts, etc.)
- FAQ
- Architecture diagrams

**Length:** 18 KB, comprehensive, covers everything

### **QUICK_REFERENCE.md** (Cheat Sheet)
- Most common tasks
- One-liner command reference table
- Database query templates
- Environment setup checklist
- Quick troubleshooting table

**Length:** 2.5 KB, tables and quick lookups

---

## 📊 Topic-to-Document Mapping

| If You Want To... | Read This Section | In This File |
|-------------------|-------------------|--------------|
| Analyze an issue | Quick Start | README_SENTRY_USAGE.md |
| List analyses | CLI Commands → List Stored Alerts | README_SENTRY_USAGE.md |
| Show details | CLI Commands → Show Full Analysis | README_SENTRY_USAGE.md |
| Set up Slack daemon | Daemon Mode | README_SENTRY_USAGE.md |
| Query the database | Data Storage → Querying the Database | README_SENTRY_USAGE.md |
| Batch analyze | Real Examples → Example 1 | README_SENTRY_USAGE.md |
| Find high-frequency issues | Real Examples → Example 2 | README_SENTRY_USAGE.md |
| Export analyses | Real Examples → Example 4 | README_SENTRY_USAGE.md |
| See what Claude receives | Real Examples → Example 5 | README_SENTRY_USAGE.md |
| Fix SSL errors | Troubleshooting → SSL Certificate Error | README_SENTRY_USAGE.md |
| Fix model errors | Troubleshooting → Model Not Allowed | README_SENTRY_USAGE.md |
| Understand the system | Architecture | README_SENTRY_USAGE.md |
| Quick command ref | One-Liner Reference | QUICK_REFERENCE.md |
| Check database | Database Queries | QUICK_REFERENCE.md |

---

## 💾 Key Locations

| What | Location |
|------|----------|
| **Project root** | `/Users/ishan.shah/projects/ai-alert/` |
| **Configuration** | `~/.ai-alert/config.yaml` |
| **Database** | `~/.ai-alert/data.db` (SQLite) |
| **Logs** | `~/.ai-alert/logs/ai-alert-*.log` |
| **Tokens** | `/Users/ishan.shah/projects/ai-alert/.env` |
| **SSL wrapper** | `/Users/ishan.shah/projects/ai-alert/ai-alert-ssl` |

---

## ⚡ Most Common Commands

```bash
# Analyze
./ai-alert-ssl analyze 7691078133
./ai-alert-ssl analyze 7691078133 --force      # Re-analyze
./ai-alert-ssl analyze 7691078133 --dry-run    # See prompt

# List & Show
poetry run ai-alert list
poetry run ai-alert list --status pending
poetry run ai-alert show <alert-id>

# Status & Config
poetry run ai-alert status
poetry run ai-alert config-check

# Daemon
poetry run ai-alert daemon start --foreground

# Database
sqlite3 ~/.ai-alert/data.db "SELECT COUNT(*) FROM analyses;"
```

---

## 🔍 How to Use This Index

1. **Find your use case** in the topic table above
2. **Go to the recommended section** in the recommended file
3. **If something is unclear**, check:
   - README_SENTRY_USAGE.md for detailed explanation
   - QUICK_REFERENCE.md for quick lookup

---

## 📝 Quick Answers

**Q: How do I analyze a Sentry issue?**
A: `./ai-alert-ssl analyze <issue-id>`

**Q: Where are my analyses stored?**
A: `~/.ai-alert/data.db` (SQLite database)

**Q: How do I see previous analyses?**
A: `poetry run ai-alert list` then `poetry run ai-alert show <alert-id>`

**Q: How do I get Claude to analyze Slack alerts automatically?**
A: `poetry run ai-alert daemon start --foreground`

**Q: What if I get an SSL error?**
A: Use `./ai-alert-ssl` wrapper script instead of `poetry run`

**Q: Can I run multiple analyses at once?**
A: Yes, batch them: `for id in ...; do ./ai-alert-ssl analyze $id; done`

---

## 🎯 Next Steps

1. **First time?** Read: README_SENTRY_USAGE.md → Setup Requirements
2. **Ready to analyze?** Use: `./ai-alert-ssl analyze <issue-id>`
3. **Need commands?** Reference: QUICK_REFERENCE.md
4. **Got an error?** Check: README_SENTRY_USAGE.md → Troubleshooting

---

**For comprehensive guide:** See [README_SENTRY_USAGE.md](README_SENTRY_USAGE.md)

**For quick commands:** See [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
