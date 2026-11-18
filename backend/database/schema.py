from backend.database.connection import db_connection


def init_db():
    with db_connection() as conn:

        conn.execute("PRAGMA journal_mode = WAL")

        conn.executescript("""
            CREATE TABLE IF NOT EXISTS app_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (
                    strftime('%Y-%m-%dT%H:%M:%fZ','now')
                )
            );

            CREATE TABLE IF NOT EXISTS automation_settings (
                automation_key TEXT PRIMARY KEY,
                enabled INTEGER NOT NULL DEFAULT 0
                    CHECK(enabled IN (0,1)),
                settings_json TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT NOT NULL DEFAULT (
                    strftime('%Y-%m-%dT%H:%M:%fZ','now')
                )
            );

            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                severity TEXT NOT NULL
                    CHECK(severity IN (
                        'INFO','WARNING','ERROR','CRITICAL'
                    )),
                message TEXT NOT NULL,
                details TEXT,
                created_at TEXT NOT NULL DEFAULT (
                    strftime('%Y-%m-%dT%H:%M:%fZ','now')
                )
            );

            CREATE INDEX IF NOT EXISTS idx_activity_logs_date
            ON activity_logs(created_at);

            CREATE TABLE IF NOT EXISTS channel_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_event_id INTEGER NOT NULL UNIQUE,
                event_type TEXT NOT NULL
                    CHECK(event_type IN ('entry','exit')),
                telegram_user_id INTEGER NOT NULL,
                first_name TEXT,
                username TEXT,
                event_at TEXT NOT NULL,
                recorded_at TEXT NOT NULL DEFAULT (
                    strftime('%Y-%m-%dT%H:%M:%fZ','now')
                )
            );

            CREATE INDEX IF NOT EXISTS idx_channel_events_date
            ON channel_events(event_at);

            CREATE TABLE IF NOT EXISTS monitored_channel (
                id INTEGER PRIMARY KEY CHECK(id = 1),
                telegram_channel_id INTEGER UNIQUE,
                title TEXT,
                enabled INTEGER NOT NULL DEFAULT 1
                    CHECK(enabled IN (0,1)),
                updated_at TEXT NOT NULL DEFAULT (
                    strftime('%Y-%m-%dT%H:%M:%fZ','now')
                )
            );

            CREATE TABLE IF NOT EXISTS managed_contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_user_id INTEGER NOT NULL UNIQUE,
                username TEXT,
                current_first_name TEXT,
                current_last_name TEXT,
                gender_category TEXT NOT NULL
                    CHECK(gender_category IN ('male','female')),
                enabled INTEGER NOT NULL DEFAULT 1
                    CHECK(enabled IN (0,1)),
                created_at TEXT NOT NULL DEFAULT (
                    strftime('%Y-%m-%dT%H:%M:%fZ','now')
                ),
                updated_at TEXT NOT NULL DEFAULT (
                    strftime('%Y-%m-%dT%H:%M:%fZ','now')
                )
            );

            CREATE TABLE IF NOT EXISTS name_catalog (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL
                    CHECK(category IN ('male','female','surname')),
                name TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1
                    CHECK(enabled IN (0,1)),
                UNIQUE(category, name)
            );

            INSERT OR IGNORE INTO automation_settings
                (automation_key, enabled)
            VALUES
                ('welcome_messages', 0),
                ('departure_messages', 0),
                ('daily_summary', 0);

            INSERT OR IGNORE INTO monitored_channel (id)
            VALUES (1);
        """)
