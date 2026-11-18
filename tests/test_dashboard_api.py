import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch
from fastapi import HTTPException

from backend.database import connection
from backend.database.schema import init_db
from backend.api.dashboard import (
    get_dashboard_summary,
    get_recent_activity
)
from backend.api.automations import (
    list_automations,
    update_automation,
    AutomationUpdate
)


class DashboardTests(unittest.TestCase):

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

    def tearDown(self):
        self.patcher.stop()
        self.temp.cleanup()

    def test_dashboard_initial_state(self):
        result = get_dashboard_summary()

        self.assertEqual(
            result["userbot"]["status"],
            "not_configured"
        )

        self.assertIsNone(
            result["metrics"]["current_members"]
        )

        self.assertEqual(
            result["tracking_status"],
            "not_configured"
        )

    def test_automations_start_disabled(self):
        result = list_automations()

        self.assertEqual(result["count"], 3)

        for item in result["items"]:
            self.assertFalse(item["enabled"])

    def test_activate_automation(self):
        result = update_automation(
            "welcome_messages",
            AutomationUpdate(enabled=True)
        )

        self.assertTrue(result["success"])
        self.assertTrue(result["enabled"])

        automations = list_automations()["items"]

        welcome = next(
            item for item in automations
            if item["key"] == "welcome_messages"
        )

        self.assertTrue(welcome["enabled"])

    def test_automation_change_creates_activity_log(self):
        update_automation(
            "departure_messages",
            AutomationUpdate(enabled=True)
        )

        result = get_recent_activity(limit=20)

        self.assertEqual(result["count"], 1)
        self.assertIn(
            "activated",
            result["items"][0]["message"]
        )

    def test_unknown_automation_is_rejected(self):
        with self.assertRaises(HTTPException) as error:
            update_automation(
                "unknown_automation",
                AutomationUpdate(enabled=True)
            )

        self.assertEqual(error.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
