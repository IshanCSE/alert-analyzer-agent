.PHONY: help install dev test lint format clean run daemon-start daemon-stop daemon-status daemon-install daemon-uninstall

# Default target
help:
	@echo "AI Alert Agent - Available commands:"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make install         Install dependencies (production)"
	@echo "  make dev             Install dependencies (development + testing)"
	@echo ""
	@echo "Testing:"
	@echo "  make test            Run unit tests"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint            Run linting (ruff)"
	@echo "  make format          Auto-format code (black)"
	@echo ""
	@echo "Running:"
	@echo "  make run-help        Show CLI help"
	@echo ""
	@echo "Daemon Management:"
	@echo "  make daemon-start    Start daemon (foreground)"
	@echo "  make daemon-status   Check daemon status"
	@echo ""
	@echo "Setup:"
	@echo "  make setup-all       Complete setup (config + env)"
	@echo ""

# Installation targets
install:
	poetry install --no-dev

dev:
	poetry install

# Testing targets
test:
	poetry run pytest tests/ -v --tb=short

# Code quality targets
lint:
	poetry run ruff check ai_alert/ tests/

format:
	poetry run black ai_alert/ tests/

# Running targets
run-help:
	poetry run ai-alert --help

# Daemon targets
daemon-start:
	poetry run ai-alert daemon start --foreground

daemon-status:
	poetry run ai-alert status

daemon-logs:
	tail -f ~/.ai-alert/logs/daemon.out.log

# Clean target
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache dist build *.egg-info

# Setup targets
setup-config:
	@if [ ! -f ~/.ai-alert/config.yaml ]; then \
		echo "Creating config at ~/.ai-alert/config.yaml"; \
		mkdir -p ~/.ai-alert; \
		cp configs/config.example.yaml ~/.ai-alert/config.yaml; \
		echo "✅ Edit ~/.ai-alert/config.yaml with your settings"; \
	else \
		echo "Config already exists at ~/.ai-alert/config.yaml"; \
	fi

setup-env:
	@echo "Setting up environment variables..."
	@echo ""
	@echo "Required tokens:"
	@echo "  export SLACK_BOT_TOKEN='xoxb-...'"
	@echo "  export SLACK_APP_TOKEN='xapp-...'"
	@echo "  export SENTRY_API_TOKEN='sntrys_...'"
	@echo "  export ANTHROPIC_API_KEY='sk-ant-...'"
	@echo ""

setup-all: setup-config setup-env
	@echo ""
	@echo "✅ Setup complete!"

# Info targets
version:
	poetry run ai-alert version
