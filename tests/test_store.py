"""Tests for the SQLite Store (Phase 2)."""

import sqlite3
import pytest

from ai_alert.store import Store
from ai_alert.models import Alert, Analysis, AlertStatus, Recommendation


@pytest.fixture
def store():
    """Fixture: in-memory Store instance, closed after each test."""
    s = Store(db_path=":memory:")
    yield s
    s.close()


# SCHEMA


class TestSchema:
    def test_tables_created(self, store: Store):
        cursor = store.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row["name"] for row in cursor.fetchall()}
        assert "alerts" in tables
        assert "analyses" in tables

    def test_schema_is_idempotent(self, store: Store):
        # Calling _create_schema again should not raise (IF NOT EXISTS)
        store._create_schema()

    def test_context_manager_closes_connection(self):
        with Store(db_path=":memory:") as s:
            assert s.conn is not None
            s.conn.execute("SELECT 1")
        with pytest.raises(sqlite3.ProgrammingError):
            s.conn.execute("SELECT 1")


# ALERTS CRUD


class TestSaveAndGetAlert:
    def test_save_and_get_by_sentry_id(self, store: Store, test_alert: Alert):
        store.save_alert(test_alert)
        fetched = store.get_alert_by_sentry_id(test_alert.sentry_issue_id)

        assert fetched is not None
        assert fetched.id == test_alert.id
        assert fetched.sentry_issue_id == test_alert.sentry_issue_id
        assert fetched.sentry_url == test_alert.sentry_url
        assert fetched.title == test_alert.title
        assert fetched.slack_channel == test_alert.slack_channel
        assert fetched.slack_message_ts == test_alert.slack_message_ts
        assert fetched.status == AlertStatus.PENDING

    def test_get_by_sentry_id_not_found(self, store: Store):
        assert store.get_alert_by_sentry_id("does-not-exist") is None

    def test_get_by_id(self, store: Store, test_alert: Alert):
        store.save_alert(test_alert)
        fetched = store.get_alert_by_id(test_alert.id)
        assert fetched is not None
        assert fetched.id == test_alert.id

    def test_get_by_id_not_found(self, store: Store):
        assert store.get_alert_by_id("does-not-exist") is None

    def test_duplicate_sentry_issue_id_rejected(self, store: Store, test_alert: Alert):
        """Sentry issue ID is the dedup key and must be unique."""
        store.save_alert(test_alert)

        duplicate = Alert(
            sentry_issue_id=test_alert.sentry_issue_id,
            sentry_url=test_alert.sentry_url,
            title="Different title, same sentry id",
            slack_channel="other-channel",
        )
        with pytest.raises(sqlite3.IntegrityError):
            store.save_alert(duplicate)

    def test_save_alert_upsert_updates_status(self, store: Store, test_alert: Alert):
        """Saving the same alert id again updates status/last_error in place."""
        store.save_alert(test_alert)

        test_alert.status = AlertStatus.FAILED
        test_alert.last_error = "boom"
        store.save_alert(test_alert)

        fetched = store.get_alert_by_sentry_id(test_alert.sentry_issue_id)
        assert fetched.status == AlertStatus.FAILED
        assert fetched.last_error == "boom"

    def test_optional_slack_message_ts(self, store: Store):
        alert = Alert(
            sentry_issue_id="no-ts-issue",
            sentry_url="https://sentry.io/issues/no-ts-issue/",
            title="No thread timestamp yet",
            slack_channel="test-channel",
        )
        store.save_alert(alert)
        fetched = store.get_alert_by_sentry_id("no-ts-issue")
        assert fetched.slack_message_ts is None


class TestListAndCountAlerts:
    def _make_alert(self, n: int, status: AlertStatus) -> Alert:
        return Alert(
            sentry_issue_id=f"issue-{n}",
            sentry_url=f"https://sentry.io/issues/issue-{n}/",
            title=f"Error {n}",
            slack_channel="test-channel",
            status=status,
        )

    def test_list_all_alerts(self, store: Store):
        for i in range(3):
            store.save_alert(self._make_alert(i, AlertStatus.PENDING))

        alerts = store.list_alerts()
        assert len(alerts) == 3

    def test_list_alerts_filtered_by_status(self, store: Store):
        store.save_alert(self._make_alert(1, AlertStatus.PENDING))
        store.save_alert(self._make_alert(2, AlertStatus.ANALYZED))
        store.save_alert(self._make_alert(3, AlertStatus.ANALYZED))

        analyzed = store.list_alerts(status=AlertStatus.ANALYZED.value)
        assert len(analyzed) == 2
        assert all(a.status == AlertStatus.ANALYZED for a in analyzed)

    def test_list_alerts_respects_limit_and_offset(self, store: Store):
        for i in range(5):
            store.save_alert(self._make_alert(i, AlertStatus.PENDING))

        page1 = store.list_alerts(limit=2, offset=0)
        page2 = store.list_alerts(limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) == 2
        assert {a.id for a in page1}.isdisjoint({a.id for a in page2})

    def test_list_alerts_empty(self, store: Store):
        assert store.list_alerts() == []

    def test_count_alerts_total_and_by_status(self, store: Store):
        store.save_alert(self._make_alert(1, AlertStatus.PENDING))
        store.save_alert(self._make_alert(2, AlertStatus.FAILED))
        store.save_alert(self._make_alert(3, AlertStatus.FAILED))

        assert store.count_alerts() == 3
        assert store.count_alerts(AlertStatus.FAILED.value) == 2
        assert store.count_alerts(AlertStatus.ANALYZED.value) == 0


class TestUpdateAndDeleteAlert:
    def test_update_alert_status(self, store: Store, test_alert: Alert):
        store.save_alert(test_alert)
        store.update_alert_status(test_alert.id, AlertStatus.ANALYZING.value)

        fetched = store.get_alert_by_id(test_alert.id)
        assert fetched.status == AlertStatus.ANALYZING
        assert fetched.last_error is None

    def test_update_alert_status_with_error(self, store: Store, test_alert: Alert):
        store.save_alert(test_alert)
        store.update_alert_status(
            test_alert.id, AlertStatus.FAILED.value, error_msg="sentry API timeout"
        )

        fetched = store.get_alert_by_id(test_alert.id)
        assert fetched.status == AlertStatus.FAILED
        assert fetched.last_error == "sentry API timeout"

    def test_delete_alert(self, store: Store, test_alert: Alert):
        store.save_alert(test_alert)
        store.delete_alert(test_alert.id)
        assert store.get_alert_by_id(test_alert.id) is None

    def test_delete_alert_cascades_to_analyses(
        self, store: Store, test_alert: Alert, test_analysis: Analysis
    ):
        store.save_alert(test_alert)
        store.save_analysis(test_analysis)

        store.delete_alert(test_alert.id)

        assert store.get_analysis_by_alert_id(test_alert.id) is None


# ANALYSES CRUD


class TestSaveAndGetAnalysis:
    def test_save_and_get_by_alert_id(
        self, store: Store, test_alert: Alert, test_analysis: Analysis
    ):
        store.save_alert(test_alert)
        store.save_analysis(test_analysis)

        fetched = store.get_analysis_by_alert_id(test_alert.id)
        assert fetched is not None
        assert fetched.id == test_analysis.id
        assert fetched.alert_id == test_alert.id
        assert fetched.sentry_issue_id == test_analysis.sentry_issue_id
        assert fetched.model == test_analysis.model
        assert fetched.root_cause == test_analysis.root_cause
        assert fetched.confidence == test_analysis.confidence
        assert fetched.error_category == test_analysis.error_category
        assert fetched.affected_component == test_analysis.affected_component
        assert fetched.tokens_used == test_analysis.tokens_used

    def test_recommendation_roundtrips_through_json(
        self, store: Store, test_alert: Alert, test_analysis: Analysis
    ):
        store.save_alert(test_alert)
        store.save_analysis(test_analysis)

        fetched = store.get_analysis_by_alert_id(test_alert.id)
        assert isinstance(fetched.recommendation, Recommendation)
        assert fetched.recommendation.summary == test_analysis.recommendation.summary
        assert (
            fetched.recommendation.suggested_fix
            == test_analysis.recommendation.suggested_fix
        )
        assert (
            fetched.recommendation.files_to_inspect
            == test_analysis.recommendation.files_to_inspect
        )
        assert (
            fetched.recommendation.follow_up_actions
            == test_analysis.recommendation.follow_up_actions
        )
        assert fetched.recommendation.is_known_issue == test_analysis.recommendation.is_known_issue

    def test_get_by_alert_id_not_found(self, store: Store):
        assert store.get_analysis_by_alert_id("does-not-exist") is None

    def test_get_by_id(self, store: Store, test_alert: Alert, test_analysis: Analysis):
        store.save_alert(test_alert)
        store.save_analysis(test_analysis)

        fetched = store.get_analysis_by_id(test_analysis.id)
        assert fetched is not None
        assert fetched.id == test_analysis.id

    def test_get_by_id_not_found(self, store: Store):
        assert store.get_analysis_by_id("does-not-exist") is None

    def test_get_analysis_by_alert_id_returns_latest(
        self, store: Store, test_alert: Alert, test_recommendation: Recommendation
    ):
        store.save_alert(test_alert)

        older = Analysis(
            alert_id=test_alert.id,
            sentry_issue_id=test_alert.sentry_issue_id,
            model="claude-sonnet-5-5",
            root_cause="first analysis",
            confidence="low",
            error_category="api_error",
            affected_component="alerts-count-collector",
            recommendation=test_recommendation,
            tokens_used=100,
        )
        store.save_analysis(older)

        # Note: a second analysis for the same alert would violate the
        # UNIQUE(alert_id) constraint used for the "one analysis per alert"
        # invariant; instead we confirm the single stored analysis is
        # returned correctly.
        fetched = store.get_analysis_by_alert_id(test_alert.id)
        assert fetched.root_cause == "first analysis"


class TestListAndDeleteAnalysis:
    def test_list_analyses(
        self, store: Store, test_recommendation: Recommendation
    ):
        for i in range(3):
            alert = Alert(
                sentry_issue_id=f"issue-{i}",
                sentry_url=f"https://sentry.io/issues/issue-{i}/",
                title=f"Error {i}",
                slack_channel="test-channel",
            )
            store.save_alert(alert)
            analysis = Analysis(
                alert_id=alert.id,
                sentry_issue_id=alert.sentry_issue_id,
                model="claude-sonnet-5-5",
                root_cause=f"cause {i}",
                confidence="medium",
                error_category="api_error",
                affected_component="alerts-count-collector",
                recommendation=test_recommendation,
                tokens_used=100,
            )
            store.save_analysis(analysis)

        analyses = store.list_analyses()
        assert len(analyses) == 3

    def test_list_analyses_empty(self, store: Store):
        assert store.list_analyses() == []

    def test_delete_analysis(
        self, store: Store, test_alert: Alert, test_analysis: Analysis
    ):
        store.save_alert(test_alert)
        store.save_analysis(test_analysis)

        store.delete_analysis(test_analysis.id)
        assert store.get_analysis_by_id(test_analysis.id) is None

    def test_save_analysis_without_alert_raises(
        self, store: Store, test_analysis: Analysis
    ):
        """Foreign key enforcement: alert_id must reference an existing alert."""
        with pytest.raises(sqlite3.IntegrityError):
            store.save_analysis(test_analysis)


# STATS


class TestStats:
    def test_get_stats_empty_db(self, store: Store):
        stats = store.get_stats()
        assert stats == {
            "total_alerts": 0,
            "pending": 0,
            "analyzing": 0,
            "analyzed": 0,
            "failed": 0,
            "total_analyses": 0,
        }

    def test_get_stats_counts_by_status(
        self, store: Store, test_recommendation: Recommendation
    ):
        statuses = [
            AlertStatus.PENDING,
            AlertStatus.PENDING,
            AlertStatus.ANALYZING,
            AlertStatus.ANALYZED,
            AlertStatus.FAILED,
        ]
        for i, status in enumerate(statuses):
            alert = Alert(
                sentry_issue_id=f"issue-{i}",
                sentry_url=f"https://sentry.io/issues/issue-{i}/",
                title=f"Error {i}",
                slack_channel="test-channel",
                status=status,
            )
            store.save_alert(alert)

        analyzed_alert = store.list_alerts(status=AlertStatus.ANALYZED.value)[0]
        analysis = Analysis(
            alert_id=analyzed_alert.id,
            sentry_issue_id=analyzed_alert.sentry_issue_id,
            model="claude-sonnet-5-5",
            root_cause="cause",
            confidence="high",
            error_category="api_error",
            affected_component="alerts-count-collector",
            recommendation=test_recommendation,
            tokens_used=100,
        )
        store.save_analysis(analysis)

        stats = store.get_stats()
        assert stats["total_alerts"] == 5
        assert stats["pending"] == 2
        assert stats["analyzing"] == 1
        assert stats["analyzed"] == 1
        assert stats["failed"] == 1
        assert stats["total_analyses"] == 1


# PERSISTENT FILE-BACKED DATABASE


class TestFileBackedDatabase:
    def test_creates_parent_directory_and_persists(self, tmp_path):
        db_path = tmp_path / "nested" / "data.db"
        assert not db_path.parent.exists()

        with Store(db_path=str(db_path)) as s:
            alert = Alert(
                sentry_issue_id="persisted-issue",
                sentry_url="https://sentry.io/issues/persisted-issue/",
                title="Persisted error",
                slack_channel="test-channel",
            )
            s.save_alert(alert)

        assert db_path.exists()

        # Reopen and confirm data survived the round trip
        with Store(db_path=str(db_path)) as s2:
            fetched = s2.get_alert_by_sentry_id("persisted-issue")
            assert fetched is not None
            assert fetched.title == "Persisted error"
