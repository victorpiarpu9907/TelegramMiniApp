import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

from backend.database import connection
from backend.database.schema import init_db

from backend.services.userbot_manager import UserbotManager


class UserbotManagerTests(unittest.IsolatedAsyncioTestCase):

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

        self.manager = UserbotManager(
            api_id="",
            api_hash="",
            session=""
        )

    def tearDown(self):
        self.patcher.stop()
        self.temp.cleanup()

    def test_initial_status(self):

        status = self.manager.get_status()

        self.assertEqual(
            status["status"],
            "not_configured"
        )

        self.assertFalse(status["configured"])
        self.assertFalse(status["connected"])

    async def test_start_without_credentials(self):

        with self.assertRaises(Exception):
            await self.manager.start()

        self.assertEqual(
            self.manager.get_status()["status"],
            "not_configured"
        )

    async def test_stop_without_connection(self):

        result = await self.manager.stop()

        self.assertEqual(
            result["status"],
            "not_configured"
        )

        self.assertFalse(result["connected"])

    def test_invalid_api_id_is_not_configured(self):

        manager = UserbotManager(
            api_id="invalid",
            api_hash="fake",
            session="fake"
        )

        self.assertFalse(manager.is_configured)


if __name__ == "__main__":
    unittest.main(verbosity=2)
