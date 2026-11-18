import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError
from fastapi import HTTPException

from backend.database import connection
from backend.database.schema import init_db

from backend.api.channel import (
    read_channel_config,
    set_channel_config,
    update_tracking,
    ChannelConfigUpdate,
    TrackingUpdate
)


class ChannelConfigTests(unittest.TestCase):

    def setUp(self):

        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "channel_test.db"

        self.patcher = patch.object(
            connection,
            "DATABASE_PATH",
            self.db_path
        )

        self.patcher.start()
        init_db()

        self.admin = {"id": 123456789}

    def tearDown(self):

        self.patcher.stop()
        self.temp.cleanup()

    def test_initial_channel_is_not_configured(self):

        result = read_channel_config(self.admin)

        self.assertFalse(result["configured"])
        self.assertIsNone(
            result["channel"]["telegram_channel_id"]
        )

        self.assertEqual(
            result["telegram_validation"],
            "not_configured"
        )

    def test_save_channel_configuration(self):

        payload = ChannelConfigUpdate(
            telegram_channel_id=-1001234567890,
            title="Canal de pruebas",
            enabled=True
        )

        result = set_channel_config(
            payload,
            self.admin
        )

        self.assertTrue(result["success"])

        self.assertEqual(
            result["channel"]["telegram_channel_id"],
            -1001234567890
        )

        self.assertEqual(
            result["channel"]["title"],
            "Canal de pruebas"
        )

    def test_channel_configuration_persists(self):

        payload = ChannelConfigUpdate(
            telegram_channel_id=-1001234567890,
            title="Canal principal"
        )

        set_channel_config(payload, self.admin)

        result = read_channel_config(self.admin)

        self.assertTrue(result["configured"])

        self.assertEqual(
            result["channel"]["title"],
            "Canal principal"
        )

        self.assertFalse(
            result["history"]["backfill_completed"]
        )

    def test_tracking_can_be_paused_and_activated(self):

        set_channel_config(
            ChannelConfigUpdate(
                telegram_channel_id=-1001234567890,
                title="Canal principal"
            ),
            self.admin
        )

        paused = update_tracking(
            TrackingUpdate(enabled=False),
            self.admin
        )

        self.assertFalse(paused["tracking_enabled"])

        activated = update_tracking(
            TrackingUpdate(enabled=True),
            self.admin
        )

        self.assertTrue(activated["tracking_enabled"])

    def test_tracking_without_channel_is_rejected(self):

        with self.assertRaises(HTTPException) as error:

            update_tracking(
                TrackingUpdate(enabled=True),
                self.admin
            )

        self.assertEqual(
            error.exception.status_code,
            409
        )

    def test_positive_channel_id_is_rejected(self):

        with self.assertRaises(ValidationError):

            ChannelConfigUpdate(
                telegram_channel_id=123456789,
                title="Canal inválido"
            )

    def test_channel_change_creates_activity_log(self):

        set_channel_config(
            ChannelConfigUpdate(
                telegram_channel_id=-1001234567890,
                title="Canal de pruebas"
            ),
            self.admin
        )

        result = read_channel_config(self.admin)

        self.assertTrue(result["configured"])

        from backend.database.connection import db_connection

        with db_connection() as conn:

            count = conn.execute("""
                SELECT COUNT(*)
                FROM activity_logs
                WHERE category = 'channel'
            """).fetchone()[0]

        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
