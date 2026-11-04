"""SQLite persistence layer for AI Alert Agent."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from ai_alert.models import Alert, Analysis, AlertStatus
from ai_alert.logger import get_logger

logger = get_logger("store")


class Store:
    """SQLite-based persistence for alerts and analyses."""

    def __init__(self, db_path: str = ":memory:"):
        """Initialize Store with database connection.

        Args:
            db_path: Path to SQLite database file.
                    ":memory:" for in-memory database (testing).
                    Default creates persistent database at given path.
        """
        self.db_path = db_path
        self.conn = None
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database connection and create schema."""
        # Create parent directory if needed
        if self.db_path != ":memory:":
            db_file = Path(self.db_path)
            db_file.parent.mkdir(parents=True, exist_ok=True)

        # Open connection
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

        # Create schema
        self._create_schema()
        logger.info(f"Database initialized at {self.db_path}")

    def _create_schema(self) -> None:
        """Create database tables if they don't exist."""
        cursor = self.conn.cursor()

        # Alerts table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id TEXT PRIMARY KEY,
                sentry_issue_id TEXT UNIQUE NOT NULL,
                sentry_url TEXT NOT NULL,
                title TEXT NOT NULL,
                slack_channel TEXT NOT NULL,
                slack_message_ts TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                received_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_error TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Indices on frequently queried columns
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_alerts_sentry_issue_id ON alerts(sentry_issue_id)"
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_alerts_received_at ON alerts(received_at DESC)"
        )

        # Analyses table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                alert_id TEXT NOT NULL,
                sentry_issue_id TEXT NOT NULL,
                model TEXT NOT NULL,
                root_cause TEXT NOT NULL,
                confidence TEXT NOT NULL,
                error_category TEXT NOT NULL,
                affected_component TEXT NOT NULL,
                recommendation_json TEXT NOT NULL,
                tokens_used INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (alert_id) REFERENCES alerts(id) ON DELETE CASCADE,
                UNIQUE (alert_id)
            )
            """
        )

        # Indices on frequently queried columns
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_analyses_alert_id ON analyses(alert_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_analyses_sentry_issue_id ON analyses(sentry_issue_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_analyses_created_at ON analyses(created_at DESC)"
        )

        self.conn.commit()
        logger.debug("Database schema created/verified")

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    # ALERTS CRUD

    def save_alert(self, alert: Alert) -> None:
        """Insert or update an alert.

        Args:
            alert: Alert instance to save

        Raises:
            sqlite3.IntegrityError: If sentry_issue_id already exists and violates unique constraint
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO alerts (
                    id, sentry_issue_id, sentry_url, title, slack_channel,
                    slack_message_ts, status, received_at, last_error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    last_error = excluded.last_error,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    alert.id,
                    alert.sentry_issue_id,
                    alert.sentry_url,
                    alert.title,
                    alert.slack_channel,
                    alert.slack_message_ts,
                    alert.status.value if isinstance(alert.status, AlertStatus) else alert.status,
                    alert.received_at.isoformat(),
                    alert.last_error,
                ),
            )
            self.conn.commit()
            logger.debug(f"Alert saved: {alert.sentry_issue_id}")
        except sqlite3.IntegrityError as e:
            logger.error(f"Failed to save alert: {e}")
            raise

    def get_alert_by_sentry_id(self, sentry_issue_id: str) -> Optional[Alert]:
        """Fetch alert by Sentry issue ID.

        Args:
            sentry_issue_id: Sentry issue ID (dedup key)

        Returns:
            Alert instance or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM alerts WHERE sentry_issue_id = ? LIMIT 1",
            (sentry_issue_id,),
        )
        row = cursor.fetchone()

        if not row:
            return None

        return self._row_to_alert(row)

    def get_alert_by_id(self, alert_id: str) -> Optional[Alert]:
        """Fetch alert by ID.

        Args:
            alert_id: Alert ID

        Returns:
            Alert instance or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM alerts WHERE id = ? LIMIT 1", (alert_id,))
        row = cursor.fetchone()

        if not row:
            return None

        return self._row_to_alert(row)

    def list_alerts(
        self, status: Optional[str] = None, limit: int = 100, offset: int = 0
    ) -> List[Alert]:
        """List alerts with optional filtering.

        Args:
            status: Filter by status (pending, analyzing, analyzed, failed).
                   None to return all statuses.
            limit: Maximum number of results
            offset: Pagination offset

        Returns:
            List of Alert instances
        """
        if status:
            query = "SELECT * FROM alerts WHERE status = ? ORDER BY received_at DESC LIMIT ? OFFSET ?"
            params = (status, limit, offset)
        else:
            query = (
                "SELECT * FROM alerts ORDER BY received_at DESC LIMIT ? OFFSET ?"
            )
            params = (limit, offset)

        cursor = self.conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [self._row_to_alert(row) for row in rows]

    def count_alerts(self, status: Optional[str] = None) -> int:
        """Count alerts with optional status filter.

        Args:
            status: Filter by status. None to count all.

        Returns:
            Number of alerts
        """
        if status:
            query = "SELECT COUNT(*) as count FROM alerts WHERE status = ?"
            params = (status,)
        else:
            query = "SELECT COUNT(*) as count FROM alerts"
            params = ()

        cursor = self.conn.cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()
        return row["count"] if row else 0

    def update_alert_status(
        self, alert_id: str, status: str, error_msg: Optional[str] = None
    ) -> None:
        """Update alert status and optional error message.

        Args:
            alert_id: Alert ID
            status: New status (pending, analyzing, analyzed, failed)
            error_msg: Optional error message if status is 'failed'
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                UPDATE alerts
                SET status = ?, last_error = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, error_msg, alert_id),
            )
            self.conn.commit()
            logger.debug(f"Alert {alert_id} status updated to {status}")
        except sqlite3.Error as e:
            logger.error(f"Failed to update alert status: {e}")
            raise

    def delete_alert(self, alert_id: str) -> None:
        """Delete an alert and its associated analyses.

        Args:
            alert_id: Alert ID
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
            self.conn.commit()
            logger.debug(f"Alert {alert_id} deleted")
        except sqlite3.Error as e:
            logger.error(f"Failed to delete alert: {e}")
            raise

    # ANALYSES CRUD

    def save_analysis(self, analysis: Analysis) -> None:
        """Save an analysis.

        Args:
            analysis: Analysis instance to save
        """
        try:
            cursor = self.conn.cursor()
            recommendation_json = analysis.recommendation.model_dump_json()

            # Use REPLACE to handle re-analysis (overwrites existing analysis for same alert)
            cursor.execute(
                """
                REPLACE INTO analyses (
                    id, alert_id, sentry_issue_id, model, root_cause,
                    confidence, error_category, affected_component,
                    recommendation_json, tokens_used
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    analysis.id,
                    analysis.alert_id,
                    analysis.sentry_issue_id,
                    analysis.model,
                    analysis.root_cause,
                    analysis.confidence,
                    analysis.error_category,
                    analysis.affected_component,
                    recommendation_json,
                    analysis.tokens_used,
                ),
            )
            self.conn.commit()
            logger.debug(f"Analysis saved: {analysis.id}")
        except sqlite3.Error as e:
            logger.error(f"Failed to save analysis: {e}")
            raise

    def get_analysis_by_alert_id(self, alert_id: str) -> Optional[Analysis]:
        """Fetch latest analysis for an alert.

        Args:
            alert_id: Alert ID

        Returns:
            Analysis instance or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM analyses WHERE alert_id = ? ORDER BY created_at DESC LIMIT 1",
            (alert_id,),
        )
        row = cursor.fetchone()

        if not row:
            return None

        return self._row_to_analysis(row)

    def get_analysis_by_id(self, analysis_id: str) -> Optional[Analysis]:
        """Fetch analysis by ID.

        Args:
            analysis_id: Analysis ID

        Returns:
            Analysis instance or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM analyses WHERE id = ? LIMIT 1", (analysis_id,))
        row = cursor.fetchone()

        if not row:
            return None

        return self._row_to_analysis(row)

    def list_analyses(self, limit: int = 100, offset: int = 0) -> List[Analysis]:
        """List all analyses.

        Args:
            limit: Maximum number of results
            offset: Pagination offset

        Returns:
            List of Analysis instances
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM analyses ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = cursor.fetchall()

        return [self._row_to_analysis(row) for row in rows]

    def delete_analysis(self, analysis_id: str) -> None:
        """Delete an analysis.

        Args:
            analysis_id: Analysis ID
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM analyses WHERE id = ?", (analysis_id,))
            self.conn.commit()
            logger.debug(f"Analysis {analysis_id} deleted")
        except sqlite3.Error as e:
            logger.error(f"Failed to delete analysis: {e}")
            raise

    # HELPERS

    def _row_to_alert(self, row: sqlite3.Row) -> Alert:
        """Convert database row to Alert instance."""
        return Alert(
            id=row["id"],
            sentry_issue_id=row["sentry_issue_id"],
            sentry_url=row["sentry_url"],
            title=row["title"],
            slack_channel=row["slack_channel"],
            slack_message_ts=row["slack_message_ts"],
            status=AlertStatus(row["status"]),
            received_at=datetime.fromisoformat(row["received_at"]),
            last_error=row["last_error"],
        )

    def _row_to_analysis(self, row: sqlite3.Row) -> Analysis:
        """Convert database row to Analysis instance."""
        from ai_alert.models import Recommendation

        recommendation_dict = json.loads(row["recommendation_json"])
        recommendation = Recommendation(**recommendation_dict)

        return Analysis(
            id=row["id"],
            alert_id=row["alert_id"],
            sentry_issue_id=row["sentry_issue_id"],
            model=row["model"],
            root_cause=row["root_cause"],
            confidence=row["confidence"],
            error_category=row["error_category"],
            affected_component=row["affected_component"],
            recommendation=recommendation,
            tokens_used=row["tokens_used"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def get_stats(self) -> dict:
        """Get database statistics.

        Returns:
            Dictionary with counts by status
        """
        cursor = self.conn.cursor()

        stats = {
            "total_alerts": self.count_alerts(),
            "pending": self.count_alerts("pending"),
            "analyzing": self.count_alerts("analyzing"),
            "analyzed": self.count_alerts("analyzed"),
            "failed": self.count_alerts("failed"),
        }

        cursor.execute("SELECT COUNT(*) as count FROM analyses")
        row = cursor.fetchone()
        stats["total_analyses"] = row["count"] if row else 0

        return stats
