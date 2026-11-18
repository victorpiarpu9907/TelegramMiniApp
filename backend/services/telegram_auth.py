import base64
import binascii
import hashlib
import hmac
import json
import time

from urllib.parse import parse_qsl


ACCESS_TOKEN_TTL = 3600
INIT_DATA_MAX_AGE = 86400


def validate_telegram_init_data(
    init_data: str,
    bot_token: str,
    max_age_seconds: int = INIT_DATA_MAX_AGE,
    now: int | None = None
) -> dict:

    if not init_data or not bot_token:
        raise ValueError("Missing authentication data")

    try:
        pairs = parse_qsl(
            init_data,
            keep_blank_values=True,
            strict_parsing=True,
            max_num_fields=100
        )
    except ValueError:
        raise ValueError("Malformed authentication data")

    if not pairs or len(dict(pairs)) != len(pairs):
        raise ValueError("Invalid or duplicated parameters")

    fields = dict(pairs)

    received_hash = fields.pop("hash", None)

    if not received_hash or len(received_hash) != 64:
        raise ValueError("Missing or invalid hash")

    try:
        bytes.fromhex(received_hash)
    except ValueError:
        raise ValueError("Malformed hash")

    data_check_string = "\n".join(
        f"{key}={value}"
        for key, value in sorted(fields.items())
    )

    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode("utf-8"),
        hashlib.sha256
    ).digest()

    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise ValueError("Telegram signature verification failed")

    try:
        auth_date = int(fields["auth_date"])
        current_time = int(time.time()) if now is None else now
    except (KeyError, ValueError):
        raise ValueError("Invalid authentication date")

    if auth_date > current_time + 30:
        raise ValueError("Authentication date is in the future")

    if current_time - auth_date > max_age_seconds:
        raise ValueError("Authentication data has expired")

    try:
        user = json.loads(fields["user"])
    except (KeyError, json.JSONDecodeError):
        raise ValueError("Invalid Telegram user data")

    if not isinstance(user, dict) or not isinstance(user.get("id"), int):
        raise ValueError("Invalid Telegram user")

    return user


def _encode_base64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _decode_base64(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def issue_access_token(
    user_id: int,
    app_secret: str,
    ttl_seconds: int = ACCESS_TOKEN_TTL,
    now: int | None = None
) -> str:

    if not app_secret or ttl_seconds <= 0:
        raise ValueError("Invalid session configuration")

    current_time = int(time.time()) if now is None else now

    payload = {
        "sub": str(user_id),
        "iat": current_time,
        "exp": current_time + ttl_seconds
    }

    encoded_payload = _encode_base64(
        json.dumps(
            payload,
            separators=(",", ":"),
            sort_keys=True
        ).encode()
    )

    signature = hmac.new(
        app_secret.encode(),
        encoded_payload.encode(),
        hashlib.sha256
    ).digest()

    return f"{encoded_payload}.{_encode_base64(signature)}"


def verify_access_token(
    token: str,
    app_secret: str,
    now: int | None = None
) -> dict:

    if not token or not app_secret:
        raise ValueError("Invalid session")

    try:
        encoded_payload, received_signature = token.split(".")
        payload = json.loads(_decode_base64(encoded_payload))

        expected_signature = hmac.new(
            app_secret.encode(),
            encoded_payload.encode(),
            hashlib.sha256
        ).digest()

        received_bytes = _decode_base64(received_signature)

    except (
        ValueError,
        TypeError,
        KeyError,
        binascii.Error,
        json.JSONDecodeError
    ):
        raise ValueError("Malformed session token")

    if not hmac.compare_digest(expected_signature, received_bytes):
        raise ValueError("Invalid session signature")

    current_time = int(time.time()) if now is None else now

    try:
        issued_at = int(payload["iat"])
        expires_at = int(payload["exp"])
        subject = str(payload["sub"])
    except (KeyError, ValueError, TypeError):
        raise ValueError("Invalid session payload")

    if issued_at > current_time + 30:
        raise ValueError("Invalid session date")

    if expires_at <= current_time:
        raise ValueError("Session expired")

    if expires_at <= issued_at or expires_at - issued_at > ACCESS_TOKEN_TTL:
        raise ValueError("Invalid session lifetime")

    return payload
