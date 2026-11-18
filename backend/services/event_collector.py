import asyncio
import json
import logging

from datetime import datetime, timedelta, timezone

from backend.database.connection import db_connection


logger = logging.getLogger(__name__)


class EventCollector:

    def __init__(
        self,
        client,
        poll_interval=15,
        retry_interval=30,
        lookback_hours=24
    ):
        self.client = client
        self.poll_interval = poll_interval
        self.retry_interval = retry_interval
        self.lookback_hours = lookback_hours

        self._stopping = False
        self._channel_id = None
        self._channel_entity = None
        self._last_error = None

    @staticmethod
    def _utc(value):

        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)

        return value.astimezone(timezone.utc)

    def get_channel_config(self):

        with db_connection() as conn:
            row = conn.execute("""
                SELECT telegram_channel_id, title, enabled
                FROM monitored_channel
                WHERE id = 1
            """).fetchone()

        return dict(row) if row else None

    def get_cursor(self, channel_id):

        with db_connection() as conn:
            row = conn.execute("""
                SELECT last_event_id, history_backfill_completed
                FROM event_cursors
                WHERE channel_id = ?
            """, (channel_id,)).fetchone()

        if row is None:
            return 0, False

        return (
            int(row["last_event_id"]),
            bool(row["history_backfill_completed"])
        )

    def extract_event(self, event):

        action_name = type(event.action).__name__

        event_type = None
        user = None
        user_id = None

        # Salida voluntaria.
        if event.left:
            event_type = "exit"
            user = event.user
            user_id = getattr(user, "id", None)

        # Entrada mediante nombre público o enlace.
        elif event.joined or event.joined_by_invite:
            event_type = "entry"
            user = event.user
            user_id = getattr(user, "id", None)

        # Entrada mediante solicitud aprobada, si Telethon
        # expone este tipo de acción en el registro.
        elif "ParticipantJoinByRequest" in action_name:
            event_type = "entry"
            user = event.user
            user_id = getattr(user, "id", None)

        # Un administrador incorpora a otro participante.
        elif event.joined_invite:

            event_type = "entry"
            participant = event.new

            user_id = getattr(participant, "user_id", None)

            if user_id is None:
                peer = getattr(participant, "peer", None)
                user_id = getattr(peer, "user_id", None)

            entities = getattr(event, "entities", {})
            user = entities.get(user_id) if user_id else None

        else:
            return None

        if user_id is None:
            user_id = getattr(event, "user_id", None)

        if not user_id:
            return None

        event_date = self._utc(event.date)

        return {
            "telegram_event_id": int(event.id),
            "event_type": event_type,
            "telegram_user_id": int(user_id),
            "first_name": getattr(user, "first_name", None),
            "username": getattr(user, "username", None),
            "event_at": event_date.isoformat().replace("+00:00", "Z")
        }

    def save_batch(
        self,
        channel_id,
        records,
        max_event_id,
        history_completed=True
    ):

        inserted = 0

        with db_connection() as conn:

            for record in records:

                cursor = conn.execute("""
                    INSERT OR IGNORE INTO channel_events (
                        channel_id,
                        telegram_event_id,
                        event_type,
                        telegram_user_id,
                        first_name,
                        username,
                        event_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    channel_id,
                    record["telegram_event_id"],
                    record["event_type"],
                    record["telegram_user_id"],
                    record["first_name"],
                    record["username"],
                    record["event_at"]
                ))

                inserted += max(cursor.rowcount, 0)

            conn.execute("""
                INSERT INTO event_cursors (
                    channel_id,
                    last_event_id,
                    history_backfill_completed,
                    last_sync_at
                )
                VALUES (
                    ?, ?, ?,
                    strftime('%Y-%m-%dT%H:%M:%fZ','now')
                )

                ON CONFLICT(channel_id) DO UPDATE SET

                    last_event_id = MAX(
                        event_cursors.last_event_id,
                        excluded.last_event_id
                    ),

                    history_backfill_completed = MAX(
                        event_cursors.history_backfill_completed,
                        excluded.history_backfill_completed
                    ),

                    last_sync_at = excluded.last_sync_at
            """, (
                channel_id,
                max_event_id,
                int(history_completed)
            ))

        return inserted

    async def backfill_history(
        self,
        channel_entity,
        channel_id,
        now=None
    ):

        current_time = self._utc(
            now or datetime.now(timezone.utc)
        )

        cutoff = current_time - timedelta(
            hours=self.lookback_hours
        )

        records = []
        max_event_id = 0

        async for event in self.client.iter_admin_log(
            channel_entity,
            limit=None,
            join=True,
            leave=True,
            invite=True
        ):

            event_id = int(event.id)
            max_event_id = max(max_event_id, event_id)

            event_date = self._utc(event.date)

            # El registro viene del más reciente al más antiguo.
            if event_date < cutoff:
                break

            record = self.extract_event(event)

            if record:
                records.append(record)

        records.sort(
            key=lambda item: item["telegram_event_id"]
        )

        inserted = self.save_batch(
            channel_id,
            records,
            max_event_id,
            history_completed=True
        )

        return {
            "stored": inserted,
            "cursor": max_event_id,
            "events_found": len(records)
        }

    async def poll_new_events(
        self,
        channel_entity,
        channel_id
    ):

        last_event_id, history_completed = self.get_cursor(
            channel_id
        )

        if not history_completed:
            return await self.backfill_history(
                channel_entity,
                channel_id
            )

        records = []
        max_event_id = last_event_id

        async for event in self.client.iter_admin_log(
            channel_entity,
            limit=None,
            min_id=last_event_id,
            join=True,
            leave=True,
            invite=True
        ):

            event_id = int(event.id)
            max_event_id = max(max_event_id, event_id)

            record = self.extract_event(event)

            if record:
                records.append(record)

        records.sort(
            key=lambda item: item["telegram_event_id"]
        )

        inserted = self.save_batch(
            channel_id,
            records,
            max_event_id,
            history_completed=True
        )

        return {
            "stored": inserted,
            "cursor": max_event_id,
            "events_found": len(records)
        }

    def set_runtime_status(self, status, channel_id=None):

        details = json.dumps({
            "channel_id": channel_id
        })

        with db_connection() as conn:
            conn.execute("""
                INSERT INTO system_runtime (
                    component,
                    status,
                    last_heartbeat_at,
                    details_json
                )
                VALUES (
                    'event_collector',
                    ?,
                    strftime('%Y-%m-%dT%H:%M:%fZ','now'),
                    ?
                )

                ON CONFLICT(component) DO UPDATE SET
                    status = excluded.status,
                    last_heartbeat_at = excluded.last_heartbeat_at,
                    details_json = excluded.details_json
            """, (status, details))

    def write_log(self, severity, message, details=None):

        with db_connection() as conn:
            conn.execute("""
                INSERT INTO activity_logs (
                    category,
                    severity,
                    message,
                    details
                )
                VALUES ('event_collector', ?, ?, ?)
            """, (
                severity,
                message,
                json.dumps(details or {})
            ))

    async def run(self):

        self._stopping = False

        try:

            while not self._stopping:

                try:

                    config = self.get_channel_config()

                    if (
                        not config
                        or config["telegram_channel_id"] is None
                    ):
                        self.set_runtime_status("waiting_for_channel")
                        await asyncio.sleep(self.poll_interval)
                        continue

                    channel_id = int(
                        config["telegram_channel_id"]
                    )

                    if not config["enabled"]:
                        self.set_runtime_status(
                            "paused",
                            channel_id
                        )
                        await asyncio.sleep(self.poll_interval)
                        continue

                    if channel_id != self._channel_id:

                        self._channel_entity = (
                            await self.client.get_entity(channel_id)
                        )

                        self._channel_id = channel_id

                    last_id, history_completed = self.get_cursor(
                        channel_id
                    )

                    if not history_completed:

                        result = await self.backfill_history(
                            self._channel_entity,
                            channel_id
                        )

                        self.write_log(
                            "INFO",
                            "Initial 24-hour history import completed",
                            result
                        )

                    else:

                        await self.poll_new_events(
                            self._channel_entity,
                            channel_id
                        )

                    self._last_error = None

                    self.set_runtime_status(
                        "running",
                        channel_id
                    )

                    await asyncio.sleep(self.poll_interval)

                except asyncio.CancelledError:
                    raise

                except Exception as exc:

                    error_type = type(exc).__name__

                    self.set_runtime_status(
                        "error",
                        self._channel_id
                    )

                    # Evitar repetir el mismo error en cada consulta.
                    if error_type != self._last_error:

                        self.write_log(
                            "ERROR",
                            "Event collector encountered an error",
                            {"error_type": error_type}
                        )

                        self._last_error = error_type

                    logger.exception("Event collector error")

                    await asyncio.sleep(self.retry_interval)

        finally:

            try:
                self.set_runtime_status(
                    "stopped",
                    self._channel_id
                )
            except Exception:
                logger.exception(
                    "Could not update event collector status"
                )

    def stop(self):
        self._stopping = True
