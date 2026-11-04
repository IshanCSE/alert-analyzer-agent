"""Codebase analyzer for correlating stack frames to source code (Phase 5)."""

import subprocess
from pathlib import Path
from typing import Optional, List

from ai_alert.logger import get_logger

logger = get_logger("codebase_analyzer")


class CodebaseAnalyzer:
    """Analyzes local codebase (cx-collector) to extract code snippets and find related files."""

    def __init__(self, repo_path: str):
        """
        Initialize CodebaseAnalyzer with path to cx-collector repository.

        Args:
            repo_path: Absolute path to cx-collector clone (e.g., /Users/ishan.shah/projects/cx-collector)

        Raises:
            ValueError: If repo_path does not exist or is not a git repository
        """
        self.repo_path = Path(repo_path)

        if not self.repo_path.exists():
            raise ValueError(f"Repository path does not exist: {self.repo_path}")

        if not (self.repo_path / ".git").exists():
            raise ValueError(f"Not a git repository: {self.repo_path}")

        logger.info(f"CodebaseAnalyzer initialized with repo: {self.repo_path}")

    def extract_snippet(
        self,
        file_path: str,
        line_num: int,
        context_lines: int = 20,
    ) -> Optional[str]:
        """
        Extract code snippet from file around a given line number.

        Args:
            file_path: Relative path within repo (e.g., "internal/collector/alerts/alerts.go")
            line_num: Line number to center the snippet on
            context_lines: How many lines of context to include (total = 2*context_lines + 1)

        Returns:
            String with code snippet (line numbers included) or None if file not found
        """
        full_path = self.repo_path / file_path

        if not full_path.exists():
            logger.warning(f"File not found: {full_path}")
            return None

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except (IOError, UnicodeDecodeError) as e:
            logger.error(f"Failed to read file {full_path}: {e}")
            return None

        # Calculate window (1-indexed line_num, but 0-indexed array)
        start_idx = max(0, line_num - 1 - context_lines)
        end_idx = min(len(lines), line_num + context_lines)

        snippet_lines = []
        for i in range(start_idx, end_idx):
            # Line numbers are 1-indexed for display
            line_no = i + 1
            code_line = lines[i].rstrip("\n")
            is_target = line_no == line_num
            marker = " >>> " if is_target else "     "
            snippet_lines.append(f"{line_no:5d}{marker}{code_line}")

        snippet = "\n".join(snippet_lines)
        logger.debug(f"Extracted snippet from {file_path}:{line_num} ({len(snippet_lines)} lines)")
        return snippet

    def find_related_files(
        self,
        component_name: str,
        file_pattern: str = "*.go",
    ) -> List[str]:
        """
        Find related files matching a component name using git grep.

        Args:
            component_name: Component to search for (e.g., "alerts-count", "scanners-health")
            file_pattern: File pattern to search in (default: *.go)

        Returns:
            List of relative file paths matching the component
        """
        try:
            # Use git grep to find references to component_name
            result = subprocess.run(
                [
                    "git",
                    "-C",
                    str(self.repo_path),
                    "grep",
                    "-l",
                    component_name,
                    "--",
                    f"*.{file_pattern.lstrip('*.')}",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0 and result.stdout:
                files = result.stdout.strip().split("\n")
                logger.debug(f"Found {len(files)} files for component '{component_name}'")
                return files
            else:
                logger.debug(f"No files found for component '{component_name}'")
                return []

        except subprocess.TimeoutExpired:
            logger.error(f"git grep timed out searching for '{component_name}'")
            return []
        except Exception as e:
            logger.error(f"Failed to search for component '{component_name}': {e}")
            return []

    def find_test_files(self, source_file: str) -> List[str]:
        """
        Find test files corresponding to a source file.

        Args:
            source_file: Source file path (e.g., "internal/collector/alerts/alerts.go")

        Returns:
            List of test file paths (e.g., ["internal/collector/alerts/alerts_test.go"])
        """
        source_path = Path(source_file)

        # Standard Go test pattern: alerts.go → alerts_test.go
        test_name = source_path.stem + "_test" + source_path.suffix
        test_path = source_path.parent / test_name

        full_test_path = self.repo_path / test_path

        if full_test_path.exists():
            logger.debug(f"Found test file: {test_path}")
            return [str(test_path)]

        logger.debug(f"No test file found for {source_file}")
        return []

    def close(self):
        """Close analyzer (placeholder for resource cleanup if needed)."""
        logger.debug("CodebaseAnalyzer closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
