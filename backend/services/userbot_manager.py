import asyncio
import json
import logging

from datetime import datetime, timezone

from telethon import TelegramClient
from telethon.sessions import StringSession

from backend.config import API_ID, API_HASH, SESSION
from backend.database.connection import db_connection


logger = logging.getLogger(__name__)


class UserbotNotConfiguredError(Exception):
    pass


class UserbotConnectionError(Exception):
    pass


class UserbotManager:

    def __init__(
        self,
        api_id=None,
        api_hash=None,
        session=None,
        client_factory=None,
        heartbeat_interval=20
    ):
        self.api_id = API_ID if api_id is None else api_id
        self.api_hash = API_HASH if api_hash is None else api_hash
        self.session = SESSION if session is None else session

        self.client_factory = client_factory or TelegramClient
        self.heartbeat_interval = heartbeat_interval

        self._client = None
        self._runner_task = None
        self._heartbeat_task = None
        self._lock = asyncio.Lock()
        self._stopping = False

        self._status = (
            "stopped" if self.is_configured else "not_configured"
        )

        self._account = None
        self._last_heartbeat_at = None

    @property
    def is_configured(self):
        try:
            return (
                int(self.api_id) > 0
                and bool(self.api_hash)
                and bool(self.session)
            )
        except (ValueError, TypeError):
            return False

    def _write_runtime(self, status, heartbeat=False):

        heartbeat_at = (
            datetime.now(timezone.utc).isoformat(timespec="seconds")
            if heartbeat else None
        )

        details = json.dumps(self._account or {})

        with db_connection() as conn:
            conn.execute("""
                INSERT INTO system_runtime (
                    component,
                    status,
                    last_heartbeat_at,
                    details_json
                )
                VALUES ('userbot', ?, ?, ?)

                ON CONFLICT(component) DO UPDATE SET
                    status = excluded.status,
                    last_heartbeat_at = excluded.last_heartbeat_at,
                    details_json = excluded.details_json
            """, (status, heartbeat_at, details))

        self._last_heartbeat_at = heartbeat_at

    def _write_log(self, severity, message, details=None):

        try:
            with db_connection() as conn:
                conn.execute("""
                    INSERT INTO activity_logs (
                        category,
                        severity,
                        message,
                        details
                    )
                    VALUES ('userbot', ?, ?, ?)
                """, (
                    severity,
                    message,
                    json.dumps(details or {})
                ))
        except Exception:
            logger.exception("Could not save userbot activity log")

    def initialize(self):
        """Actualiza el estado al iniciar FastAPI."""

        self._status = (
            "stopped" if self.is_configured else "not_configured"
        )

        self._write_runtime(self._status, heartbeat=False)

    def get_status(self):

        connected = bool(
            self._client and self._client.is_connected()
        )

        return {
            "status": self._status,
            "configured": self.is_configured,
            "connected": connected,
            "account": self._account,
            "last_heartbeat_at": self._last_heartbeat_at
        }

    async def start(self):

        async with self._lock:

            if self._client is not None:
                if self._client.is_connected():
                    return self.get_status()

                raise UserbotConnectionError(
                    "Existing client requires cleanup. Stop it first."
                )

            if not self.is_configured:
                self._status = "not_configured"
                self._write_runtime(self._status)

                raise UserbotNotConfiguredError(
                    "Configure API_ID, API_HASH and SESSION first."
                )

            self._stopping = False
            self._status = "connecting"
            self._write_runtime(self._status)

            client = None

            try:
                client = self.client_factory(
                    StringSession(self.session),
                    int(self.api_id),
                    self.api_hash,
                    auto_reconnect=True,
                    connection_retries=5,
                    retry_delay=1
                )

                await client.connect()

                if not await client.is_user_authorized():
                    raise UserbotConnectionError(
                        "Telegram session is not authorized."
                    )

                me = await client.get_me()

                if me is None:
                    raise UserbotConnectionError(
                        "Could not identify the Telegram account."
                    )

                self._client = client

                self._account = {
                    "id": me.id,
                    "first_name": me.first_name or "",
                    "username": me.username
                }

                self._status = "running"

                self._write_runtime(
                    self._status,
                    heartbeat=True
                )

                self._heartbeat_task = asyncio.create_task(
                    self._heartbeat_loop(client)
                )

                self._runner_task = asyncio.create_task(
                    self._run_client(client)
                )

                self._write_log(
                    "INFO",
                    "Userbot connected successfully",
                    {"account_id": me.id}
                )

                return self.get_status()

            except Exception as exc:

                if client is not None:
                    try:
                        await client.disconnect()
                    except Exception:
                        pass

                self._client = None
                self._account = None
                self._status = "error"

                self._write_runtime(
                    self._status,
                    heartbeat=False
                )

                self._write_log(
                    "ERROR",
                    "Userbot connection failed",
                    {"error_type": type(exc).__name__}
                )

                if isinstance(exc, UserbotConnectionError):
                    raise

                raise UserbotConnectionError(
                    "Could not establish the Telegram connection."
                ) from exc

    async def _heartbeat_loop(self, client):

        try:
            while self._client is client and not self._stopping:

                if client.is_connected():
                    self._status = "running"
                else:
                    self._status = "reconnecting"

                self._write_runtime(
                    self._status,
                    heartbeat=True
                )

                await asyncio.sleep(self.heartbeat_interval)

        except asyncio.CancelledError:
            raise

        except Exception:
            logger.exception("Userbot heartbeat failed")

    async def _run_client(self, client):

        error = None

        try:
            await client.run_until_disconnected()

        except asyncio.CancelledError:
            raise

        except Exception as exc:
            error = exc

        finally:

            if self._client is client and not self._stopping:

                self._status = "error" if error else "offline"
                self._client = None

                heartbeat_task = self._heartbeat_task
                self._heartbeat_task = None
                self._runner_task = None

                if heartbeat_task:
                    heartbeat_task.cancel()
                    await asyncio.gather(
                        heartbeat_task,
                        return_exceptions=True
                    )

                self._write_runtime(
                    self._status,
                    heartbeat=False
                )

                self._write_log(
                    "ERROR" if error else "WARNING",
                    "Userbot disconnected",
                    {
                        "error_type": (
                            type(error).__name__ if error else None
                        )
                    }
                )

    async def stop(self):

        async with self._lock:

            self._stopping = True

            client = self._client
            heartbeat_task = self._heartbeat_task
            runner_task = self._runner_task

            if heartbeat_task:
                heartbeat_task.cancel()
                await asyncio.gather(
                    heartbeat_task,
                    return_exceptions=True
                )

            if client is not None:
                try:
                    await client.disconnect()
                except Exception:
                    logger.exception("Error disconnecting userbot")

            if runner_task and runner_task is not asyncio.current_task():
                await asyncio.gather(
                    runner_task,
                    return_exceptions=True
                )

            was_running = client is not None

            self._client = None
            self._heartbeat_task = None
            self._runner_task = None
            self._account = None

            self._status = (
                "stopped" if self.is_configured else "not_configured"
            )

            self._write_runtime(
                self._status,
                heartbeat=False
            )

            if was_running:
                self._write_log(
                    "INFO",
                    "Userbot stopped manually"
                )

            self._stopping = False

            return self.get_status()


userbot_manager = UserbotManager()
