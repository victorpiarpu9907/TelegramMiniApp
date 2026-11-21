import tempfile
import unittest

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from backend.database import connection
from backend.database.connection import db_connection
from backend.database.schema import init_db
from backend.api.statistics import get_statistics_summary


class StatisticsTests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patcher = patch.object(
            connection, "DATABASE_PATH", Path(self.temp.name) / "statistics.db"
        )
        self.patcher.start()
        init_db()
        self.today = datetime.now(timezone.utc).date()

    def tearDown(self):
        self.patcher.stop()
        self.temp.cleanup()

    def _configure(self, channel_id=-1001234567890):
        with db_connection() as conn:
            conn.execute(
                "UPDATE monitored_channel SET telegram_channel_id = ?, enabled = 1 WHERE id = 1",
                (channel_id,),
            )

    def _event(self, event_id, kind, days_ago=0, channel_id=-1001234567890):
        day = self.today - timedelta(days=days_ago)
        timestamp = day.isoformat() + "T12:00:00Z"
        with db_connection() as conn:
            conn.execute(
                """
                INSERT INTO channel_events
                    (channel_id, telegram_event_id, event_type,
                     telegram_user_id, first_name, username, event_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (channel_id, event_id, kind, event_id + 1000, "Prueba", None, timestamp),
            )

    def test_empty_unconfigured_channel_returns_no_real_records(self):
        data = get_statistics_summary(days=7)
        self.assertFalse(data["channel"]["configured"])
        self.assertEqual(data["metrics"]["total_events"], 0)
        self.assertEqual(len(data["daily"]), 7)
        self.assertEqual(data["recent_events"], [])
        self.assertIsNone(data["coverage"]["members_count"])

    def test_channel_isolation_and_period_boundaries(self):
        self._configure()
        self._event(1, "entry", days_ago=0)
        self._event(2, "entry", days_ago=1)
        self._event(3, "exit", days_ago=6)
        self._event(4, "entry", days_ago=7)  # periodo anterior
        self._event(5, "exit", days_ago=20)  # fuera de ambos
        self._event(6, "entry", days_ago=0, channel_id=-100222)

        data = get_statistics_summary(days=7)
        self.assertEqual(data["metrics"]["entries"], 2)
        self.assertEqual(data["metrics"]["exits"], 1)
        self.assertEqual(data["metrics"]["net"], 1)
        self.assertEqual(data["metrics"]["total_events"], 3)
        self.assertEqual(data["comparison"]["previous_entries"], 1)
        self.assertEqual(data["comparison"]["previous_exits"], 0)
        self.assertEqual(len(data["recent_events"]), 3)
        self.assertEqual(data["daily"][-1]["entries"], 1)
        self.assertEqual(data["daily"][0]["exits"], 1)

    def test_30_and_90_day_ranges_fill_empty_days(self):
        self._configure()
        for days in (30, 90):
            data = get_statistics_summary(days=days)
            self.assertEqual(len(data["daily"]), days)
            self.assertEqual(data["daily"][-1]["date"], self.today.isoformat())
            self.assertTrue(all(row["entries"] == 0 for row in data["daily"]))

    def test_recent_events_limit_and_order(self):
        self._configure()
        for i in range(20):
            self._event(i + 1, "entry")
        data = get_statistics_summary(days=7)
        self.assertEqual(len(data["recent_events"]), 15)
        self.assertEqual(data["recent_events"][0]["telegram_event_id"], 20)

    def test_history_coverage_is_per_channel(self):
        self._configure()
        with db_connection() as conn:
            conn.execute(
                """
                INSERT INTO event_cursors
                  (channel_id, last_event_id, history_backfill_completed, last_sync_at)
                VALUES (?, 10, 1, '2026-01-01T12:00:00Z')
                """, (-1001234567890,)
            )
        data = get_statistics_summary(days=7)
        self.assertTrue(data["coverage"]["history_backfill_completed"])
        self.assertEqual(data["coverage"]["last_sync_at"], "2026-01-01T12:00:00Z")


if __name__ == "__main__":
    unittest.main(verbosity=2)
