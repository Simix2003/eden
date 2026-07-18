from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 1


def migrate(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY NOT NULL, value TEXT NOT NULL)"
    )
    row = connection.execute("SELECT value FROM metadata WHERE key = 'schema_version'").fetchone()
    current = int(row[0]) if row else 0
    if current > SCHEMA_VERSION:
        raise RuntimeError(f"database schema {current} is newer than supported schema {SCHEMA_VERSION}")
    if current < 1:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at REAL NOT NULL,
                tick INTEGER NOT NULL,
                checksum TEXT NOT NULL,
                payload BLOB NOT NULL,
                complete INTEGER NOT NULL DEFAULT 0 CHECK (complete IN (0, 1))
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_complete_id ON snapshots(complete, id DESC)")
        connection.execute(
            "INSERT INTO metadata(key, value) VALUES('schema_version', '1') "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value"
        )
    connection.commit()

