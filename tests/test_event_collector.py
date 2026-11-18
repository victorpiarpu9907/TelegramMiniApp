import tempfile
import unittest

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.database import connection
from backend.database.connection import db_connection
from backend.database.schema import init_db
from backend.services.event_collector import EventCollector


class FakeEvent:

    def __init__(
        self,
        event_id,
        date,
        kind,
        user,
        target=None
    ):
        self.id = event_id
        self.date = date
        self.user = user
        self.user_id = user.id if user else 0

        self.joined = kind == "join"
        self.left = kind == "leave"
        self.joined_by_invite = kind == "join_by_invite"
        self.joined_invite = kind == "invite"

        self.new = None
        self.entities = {}

        if kind == "invite":
            self.action = type(
                "ChannelAdminLogEventActionParticipantInvite",
                (),
                {}
            )()

            self.new = SimpleNamespace(
                user_id=target.id
            )

            self.entities[target.id] = target

        elif kind == "join_request":
            self.action = type(
                "ChannelAdminLogEventActionParticipantJoinByRequest",
                (),
                {}
            )()

        elif kind == "leave":
            self.action = type(
                "ChannelAdminLogEventActionParticipantLeave",
                (),
                {}
            )()

        else:
            self.action = type(
                "ChannelAdminLogEventActionParticipantJoin",
                (),
                {}
            )()


class FakeClient:

    def __init__(self, events):
        self.events = events
        self.calls = []

    def iter_admin_log(self, entity, **kwargs):

        self.calls.append(kwargs)

        min_id = kwargs.get("min_id", 0)

        selected = [
            event for event in self.events
            if event.id > min_id
        ]

        async def generate():
            for event in selected:
                yield event

        return generate()


class EventCollectorTests(unittest.IsolatedAsyncioTestCase):

    def setUp(self):

        self.temp = tempfile.TemporaryDirectory()

        self.db_path = Path(self.temp.name) / "test.db"

        self.patcher = patch.object(
            connection,
            "DATABASE_PATH",
            self.db_path
        )

        self.patcher.start()

        init_db()

        self.channel_id = -100123456789

    def tearDown(self):
        self.patcher.stop()
        self.temp.cleanup()

    async def test_backfill_imports_only_last_24_hours(self):

        now = datetime(
            2026, 11, 18, 12, 0,
            tzinfo=timezone.utc
        )

        user1 = SimpleNamespace(
            id=101,
            first_name="Carlos",
            username="carlos"
        )

        user2 = SimpleNamespace(
            id=102,
            first_name="Maria",
            username="maria"
        )

        user3 = SimpleNamespace(
            id=103,
            first_name="Pedro",
            username="pedro"
        )

        client = FakeClient([
            FakeEvent(105, now - timedelta(hours=1), "join", user1),
            FakeEvent(104, now - timedelta(hours=2), "leave", user2),
            FakeEvent(103, now - timedelta(hours=25), "join", user3),
        ])

        collector = EventCollector(client)

        result = await collector.backfill_history(
            "fake-channel",
            self.channel_id,
            now=now
        )

        self.assertEqual(result["stored"], 2)
        self.assertEqual(result["cursor"], 105)

        with db_connection() as conn:

            rows = conn.execute("""
                SELECT telegram_event_id, event_type
                FROM channel_events
                WHERE channel_id = ?
                ORDER BY telegram_event_id
            """, (self.channel_id,)).fetchall()

            cursor = conn.execute("""
                SELECT last_event_id, history_backfill_completed
                FROM event_cursors
                WHERE channel_id = ?
            """, (self.channel_id,)).fetchone()

        self.assertEqual(len(rows), 2)

        self.assertEqual(rows[0]["event_type"], "exit")
        self.assertEqual(rows[1]["event_type"], "entry")

        self.assertEqual(cursor["last_event_id"], 105)
        self.assertEqual(cursor["history_backfill_completed"], 1)

    async def test_invite_records_actual_member_not_admin(self):

        now = datetime.now(timezone.utc)

        admin = SimpleNamespace(
            id=999,
            first_name="Administrator",
            username="admin"
        )

        invited_user = SimpleNamespace(
            id=555,
            first_name="Invited",
            username="invited_user"
        )

        event = FakeEvent(
            200,
            now,
            "invite",
            admin,
            target=invited_user
        )

        collector = EventCollector(FakeClient([event]))

        result = await collector.backfill_history(
            "fake-channel",
            self.channel_id
        )

        self.assertEqual(result["stored"], 1)

        with db_connection() as conn:
            row = conn.execute("""
                SELECT telegram_user_id, first_name
                FROM channel_events
                WHERE channel_id = ?
            """, (self.channel_id,)).fetchone()

        self.assertEqual(row["telegram_user_id"], 555)
        self.assertEqual(row["first_name"], "Invited")

    async def test_poll_uses_cursor_and_prevents_duplicates(self):

        now = datetime.now(timezone.utc)

        user1 = SimpleNamespace(
            id=201,
            first_name="Juan",
            username="juan"
        )

        user2 = SimpleNamespace(
            id=202,
            first_name="Ana",
            username="ana"
        )

        client = FakeClient([
            FakeEvent(12, now, "join", user1),
            FakeEvent(11, now, "leave", user2)
        ])

        collector = EventCollector(client)

        collector.save_batch(
            self.channel_id,
            [],
            max_event_id=10,
            history_completed=True
        )

        first = await collector.poll_new_events(
            "fake-channel",
            self.channel_id
        )

        second = await collector.poll_new_events(
            "fake-channel",
            self.channel_id
        )

        self.assertEqual(first["stored"], 2)
        self.assertEqual(first["cursor"], 12)

        self.assertEqual(second["stored"], 0)

        self.assertEqual(client.calls[0]["min_id"], 10)
        self.assertEqual(client.calls[1]["min_id"], 12)

        with db_connection() as conn:
            count = conn.execute("""
                SELECT COUNT(*)
                FROM channel_events
                WHERE channel_id = ?
            """, (self.channel_id,)).fetchone()[0]

        self.assertEqual(count, 2)

    def test_migrates_old_channel_events_table(self):

        with db_connection() as conn:

            conn.execute("DROP TABLE channel_events")

            conn.execute("""
                CREATE TABLE channel_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_event_id INTEGER NOT NULL UNIQUE,
                    event_type TEXT NOT NULL,
                    telegram_user_id INTEGER NOT NULL,
                    first_name TEXT,
                    username TEXT,
                    event_at TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                )
            """)

            conn.execute("""
                INSERT INTO channel_events (
                    telegram_event_id,
                    event_type,
                    telegram_user_id,
                    first_name,
                    event_at,
                    recorded_at
                )
                VALUES (
                    5, 'entry', 123, 'Legacy',
                    '2026-11-18T10:00:00Z',
                    '2026-11-18T10:00:00Z'
                )
            """)

            conn.execute("""
                CREATE INDEX idx_channel_events_date
                ON channel_events(event_at)
            """)

        init_db()

        with db_connection() as conn:

            columns = {
                row["name"]
                for row in conn.execute(
                    "PRAGMA table_info(channel_events)"
                ).fetchall()
            }

            row = conn.execute("""
                SELECT channel_id, telegram_event_id
                FROM channel_events
                WHERE telegram_event_id = 5
            """).fetchone()

        self.assertIn("channel_id", columns)
        self.assertEqual(row["channel_id"], 0)
        self.assertEqual(row["telegram_event_id"], 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
