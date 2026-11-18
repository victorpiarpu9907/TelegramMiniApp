import hashlib
import hmac
import json
import unittest

from urllib.parse import urlencode

from backend.services.telegram_auth import (
    validate_telegram_init_data,
    issue_access_token,
    verify_access_token
)


TEST_BOT_TOKEN = "123456789:FAKE_TEST_TOKEN_NOT_REAL"
TEST_SECRET = "fake-local-secret-for-unit-tests"
TEST_TIME = 1700000000
TEST_USER_ID = 987654321


def generate_test_init_data(user_id, auth_date=TEST_TIME):

    fields = {
        "auth_date": str(auth_date),
        "query_id": "test-query",
        "user": json.dumps({
            "id": user_id,
            "first_name": "Test",
            "username": "test_user"
        }, separators=(",", ":"))
    }

    data_check_string = "\n".join(
        f"{key}={value}"
        for key, value in sorted(fields.items())
    )

    secret_key = hmac.new(
        b"WebAppData",
        TEST_BOT_TOKEN.encode(),
        hashlib.sha256
    ).digest()

    fields["hash"] = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256
    ).hexdigest()

    return urlencode(fields)


class TelegramAuthTests(unittest.TestCase):

    def test_valid_telegram_data(self):
        data = generate_test_init_data(TEST_USER_ID)

        user = validate_telegram_init_data(
            data,
            TEST_BOT_TOKEN,
            now=TEST_TIME
        )

        self.assertEqual(user["id"], TEST_USER_ID)

    def test_rejects_modified_data(self):
        data = generate_test_init_data(TEST_USER_ID)
        data = data.replace("test-query", "modified-query")

        with self.assertRaises(ValueError):
            validate_telegram_init_data(
                data,
                TEST_BOT_TOKEN,
                now=TEST_TIME
            )

    def test_rejects_expired_data(self):
        data = generate_test_init_data(
            TEST_USER_ID,
            auth_date=TEST_TIME - 90000
        )

        with self.assertRaises(ValueError):
            validate_telegram_init_data(
                data,
                TEST_BOT_TOKEN,
                now=TEST_TIME
            )

    def test_session_token(self):
        token = issue_access_token(
            TEST_USER_ID,
            TEST_SECRET,
            now=TEST_TIME
        )

        payload = verify_access_token(
            token,
            TEST_SECRET,
            now=TEST_TIME + 10
        )

        self.assertEqual(payload["sub"], str(TEST_USER_ID))

    def test_rejects_modified_session(self):
        token = issue_access_token(
            TEST_USER_ID,
            TEST_SECRET,
            now=TEST_TIME
        )

        modified_token = token[:-1] + (
            "A" if token[-1] != "A" else "B"
        )

        with self.assertRaises(ValueError):
            verify_access_token(
                modified_token,
                TEST_SECRET,
                now=TEST_TIME
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
