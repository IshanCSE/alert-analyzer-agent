"""Tests for CodebaseAnalyzer (Phase 5)."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import subprocess

from ai_alert.services.codebase_analyzer import CodebaseAnalyzer


@pytest.fixture
def repo_path(tmp_path):
    """Fixture: Create a temporary git repository for testing."""
    repo = tmp_path / "test_repo"
    repo.mkdir()

    # Initialize as git repo
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)

    # Create some test files
    src_dir = repo / "internal" / "collector" / "alerts"
    src_dir.mkdir(parents=True)

    alerts_file = src_dir / "alerts.go"
    alerts_file.write_text(
        """package alerts

import "fmt"

// AlertCollector collects alerts
type AlertCollector struct {
    name string
}

func (a *AlertCollector) Run(ctx context.Context) error {
    // Line 10: Collect alerts from Sentry
    alerts, err := a.client.GetAlerts(ctx)
    if err != nil {
        return fmt.Errorf("alerts-count-collector: failed to fetch: %w", err)
    }

    // Line 15: Process alerts
    for _, alert := range alerts {
        // Line 17: Check for nil pointer
        if alert == nil {
            continue
        }

        // Line 21: Extract fields
        severity := alert.Severity
        message := alert.Message
    }

    return nil
}
""",
        encoding="utf-8",
    )

    # Create test file
    alerts_test = src_dir / "alerts_test.go"
    alerts_test.write_text(
        """package alerts

import "testing"

func TestAlertCollector(t *testing.T) {
    // Test implementation
}
""",
        encoding="utf-8",
    )

    # Stage files in git
    subprocess.run(["git", "add", "-A"], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo,
        capture_output=True,
        check=True,
        env={**subprocess.os.environ, "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@test.com",
             "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@test.com"},
    )

    return repo


# INITIALIZATION


class TestCodebaseAnalyzerInitialization:
    def test_init_valid_repo(self, repo_path):
        """Test initialization with valid git repository."""
        analyzer = CodebaseAnalyzer(str(repo_path))
        assert analyzer.repo_path == repo_path

    def test_init_nonexistent_path_raises(self, tmp_path):
        """Test initialization fails with nonexistent path."""
        fake_path = tmp_path / "does_not_exist"
        with pytest.raises(ValueError, match="does not exist"):
            CodebaseAnalyzer(str(fake_path))

    def test_init_non_git_repo_raises(self, tmp_path):
        """Test initialization fails with non-git directory."""
        non_git = tmp_path / "not_a_repo"
        non_git.mkdir()
        with pytest.raises(ValueError, match="Not a git repository"):
            CodebaseAnalyzer(str(non_git))


# EXTRACT SNIPPET


class TestExtractSnippet:
    def test_extract_snippet_success(self, repo_path):
        """Test successful code snippet extraction."""
        analyzer = CodebaseAnalyzer(str(repo_path))

        snippet = analyzer.extract_snippet(
            "internal/collector/alerts/alerts.go",
            line_num=10,
            context_lines=3,
        )

        assert snippet is not None
        assert "10 >>>" in snippet  # Target line marked
        assert "func" in snippet  # Should contain Go code

    def test_extract_snippet_marks_target_line(self, repo_path):
        """Test that target line is marked with >>>."""
        analyzer = CodebaseAnalyzer(str(repo_path))

        snippet = analyzer.extract_snippet(
            "internal/collector/alerts/alerts.go",
            line_num=15,
            context_lines=2,
        )

        lines = snippet.split("\n")
        marked_line = [l for l in lines if ">>>" in l]
        assert len(marked_line) == 1
        assert "15" in marked_line[0]

    def test_extract_snippet_respects_context_window(self, repo_path):
        """Test that context_lines parameter is respected."""
        analyzer = CodebaseAnalyzer(str(repo_path))

        snippet = analyzer.extract_snippet(
            "internal/collector/alerts/alerts.go",
            line_num=15,
            context_lines=2,
        )

        lines = snippet.split("\n")
        # Should have 5 lines total (2 before + target + 2 after)
        assert len(lines) == 5

    def test_extract_snippet_beginning_of_file(self, repo_path):
        """Test extraction near beginning of file (no pre-context)."""
        analyzer = CodebaseAnalyzer(str(repo_path))

        snippet = analyzer.extract_snippet(
            "internal/collector/alerts/alerts.go",
            line_num=1,
            context_lines=3,
        )

        assert snippet is not None
        lines = snippet.split("\n")
        # Should include line 1 and context after, but not before
        assert len(lines) >= 1

    def test_extract_snippet_end_of_file(self, repo_path):
        """Test extraction near end of file (no post-context)."""
        analyzer = CodebaseAnalyzer(str(repo_path))

        snippet = analyzer.extract_snippet(
            "internal/collector/alerts/alerts.go",
            line_num=35,  # File is ~30 lines, so this is past the end
            context_lines=5,
        )

        assert snippet is not None
        # Should gracefully handle line beyond EOF

    def test_extract_snippet_nonexistent_file(self, repo_path):
        """Test extraction fails gracefully for nonexistent file."""
        analyzer = CodebaseAnalyzer(str(repo_path))

        snippet = analyzer.extract_snippet(
            "internal/collector/nonexistent.go",
            line_num=10,
        )

        assert snippet is None

    def test_extract_snippet_with_context_manager(self, repo_path):
        """Test extract_snippet works within context manager."""
        with CodebaseAnalyzer(str(repo_path)) as analyzer:
            snippet = analyzer.extract_snippet(
                "internal/collector/alerts/alerts.go",
                line_num=10,
                context_lines=2,
            )

        assert snippet is not None


# FIND RELATED FILES


class TestFindRelatedFiles:
    def test_find_related_files_component_found(self, repo_path):
        """Test finding files that reference a component."""
        analyzer = CodebaseAnalyzer(str(repo_path))

        files = analyzer.find_related_files("alerts-count")

        assert len(files) > 0
        assert any("alerts.go" in f for f in files)

    def test_find_related_files_not_found(self, repo_path):
        """Test finding files for non-existent component."""
        analyzer = CodebaseAnalyzer(str(repo_path))

        files = analyzer.find_related_files("nonexistent-component-xyz")

        assert isinstance(files, list)
        assert len(files) == 0

    def test_find_related_files_returns_list(self, repo_path):
        """Test find_related_files always returns a list."""
        analyzer = CodebaseAnalyzer(str(repo_path))

        result = analyzer.find_related_files("any-component")

        assert isinstance(result, list)

    @patch("subprocess.run")
    def test_find_related_files_timeout(self, mock_run, repo_path):
        """Test handling of git grep timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("git grep", 10)

        analyzer = CodebaseAnalyzer(str(repo_path))
        files = analyzer.find_related_files("component")

        assert files == []

    @patch("subprocess.run")
    def test_find_related_files_git_error(self, mock_run, repo_path):
        """Test handling of git command errors."""
        mock_run.side_effect = Exception("git error")

        analyzer = CodebaseAnalyzer(str(repo_path))
        files = analyzer.find_related_files("component")

        assert files == []


# FIND TEST FILES


class TestFindTestFiles:
    def test_find_test_files_success(self, repo_path):
        """Test finding test file for source file."""
        analyzer = CodebaseAnalyzer(str(repo_path))

        test_files = analyzer.find_test_files("internal/collector/alerts/alerts.go")

        assert len(test_files) == 1
        assert "alerts_test.go" in test_files[0]

    def test_find_test_files_nonexistent_source(self, repo_path):
        """Test finding test file for nonexistent source."""
        analyzer = CodebaseAnalyzer(str(repo_path))

        test_files = analyzer.find_test_files("internal/collector/nonexistent.go")

        assert test_files == []

    def test_find_test_files_returns_list(self, repo_path):
        """Test find_test_files always returns a list."""
        analyzer = CodebaseAnalyzer(str(repo_path))

        result = analyzer.find_test_files("internal/collector/alerts/alerts.go")

        assert isinstance(result, list)


# RESOURCE MANAGEMENT


class TestCodebaseAnalyzerResourceManagement:
    def test_context_manager(self, repo_path):
        """Test context manager protocol."""
        with CodebaseAnalyzer(str(repo_path)) as analyzer:
            assert analyzer.repo_path == repo_path
        # Should exit cleanly

    def test_close_method(self, repo_path):
        """Test close method."""
        analyzer = CodebaseAnalyzer(str(repo_path))
        analyzer.close()  # Should not raise


# INTEGRATION


class TestCodebaseAnalyzerIntegration:
    def test_full_workflow(self, repo_path):
        """Test complete workflow: extract snippet and find related files."""
        with CodebaseAnalyzer(str(repo_path)) as analyzer:
            # Extract snippet
            snippet = analyzer.extract_snippet(
                "internal/collector/alerts/alerts.go",
                line_num=15,
                context_lines=3,
            )
            assert snippet is not None

            # Find related files
            files = analyzer.find_related_files("alerts-count")
            assert len(files) >= 1

            # Find test files
            test_files = analyzer.find_test_files(files[0])
            # May or may not find test file depending on naming
            assert isinstance(test_files, list)
