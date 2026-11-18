import asyncio
import tempfile
import unittest

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.database import connection
from backend.database.connection import db_connection
from backend.database.schema import init_db
from backend.services.userbot_manager import UserbotManager


class FakeTelegramClient:

    def __init__(self, *args, **kwargs):
        self.connected = False
        self.disconnected = asyncio.Event()

    async def connect(self):
        self.connected = True

    async def is_user_authorized(self):
        return True

    async def get_me(self):
        return SimpleNamespace(
            id=123456789,
            first_name="Test",
            username="test_account"
        )

    def is_connected(self):
        return self.connected

    async def run_until_disconnected(self):
        await self.disconnected.wait()

    async def disconnect(self):
        self.connected = False
        self.disconnected.set()


class UserbotCollectorIntegrationTests(
    unittest.IsolatedAsyncioTestCase
):

    def setUp(self):

        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "integration.db"

        self.patcher = patch.object(
            connection,
            "DATABASE_PATH",
            self.db_path
        )

        self.patcher.start()
        init_db()

        self.manager = UserbotManager(
            api_id="12345",
            api_hash="fake-test-hash",
            session="fake-test-session",
            client_factory=FakeTelegramClient,
            heartbeat_interval=0.05
        )

    def tearDown(self):
        self.patcher.stop()
        self.temp.cleanup()

    async def start_fake_userbot(self):

        session_patcher = patch(
            "backend.services.userbot_manager.StringSession",
            return_value="fake-session-object"
        )

        session_patcher.start()
        self.addCleanup(session_patcher.stop)

        return await self.manager.start()

    async def test_collector_starts_and_stops_with_userbot(self):

        result = await self.start_fake_userbot()

        self.assertEqual(result["status"], "running")
        self.assertTrue(result["connected"])

        await asyncio.sleep(0.05)

        status = self.manager.get_status()

        self.assertEqual(
            status["event_collector"]["status"],
            "waiting_for_channel"
        )

        stopped = await self.manager.stop()

        self.assertEqual(stopped["status"], "stopped")

        self.assertEqual(
            stopped["event_collector"]["status"],
            "stopped"
        )

    async def test_unexpected_disconnect_stops_collector(self):

        await self.start_fake_userbot()

        await asyncio.sleep(0.05)

        runner = self.manager._runner_task
        client = self.manager._client

        await client.disconnect()

        await asyncio.wait_for(runner, timeout=2)

        status = self.manager.get_status()

        self.assertEqual(status["status"], "offline")
        self.assertFalse(status["connected"])

        self.assertEqual(
            status["event_collector"]["status"],
            "offline"
        )

        with db_connection() as conn:

            rows = conn.execute("""
                SELECT component, status
                FROM system_runtime
                ORDER BY component
            """).fetchall()

        states = {
            row["component"]: row["status"]
            for row in rows
        }

        self.assertEqual(states["userbot"], "offline")
        self.assertEqual(states["event_collector"], "offline")


if __name__ == "__main__":
    unittest.main(verbosity=2)
