"""Small forward migrations for local SQLite databases."""

from __future__ import annotations

import sqlite3


def migrate(connection: sqlite3.Connection) -> None:
    """Add columns introduced after the initial persistence slice."""

    additions = {
        "runs": {
            "business_outcome": "TEXT",
            "pause_reason": "TEXT",
            "pause_data": "TEXT NOT NULL DEFAULT '{}'",
            "error_type": "TEXT",
            "error_message": "TEXT",
            "tool_calls": "INTEGER NOT NULL DEFAULT 0",
            "max_steps": "INTEGER NOT NULL DEFAULT 10",
            "max_tool_calls": "INTEGER NOT NULL DEFAULT 20",
        },
        "steps": {
            "pause_reason": "TEXT",
            "attempt_count": "INTEGER NOT NULL DEFAULT 0",
            "tool_name": "TEXT",
            "idempotency_key": "TEXT",
            "error_type": "TEXT",
            "error_message": "TEXT",
        },
    }
    for table, columns_to_add in additions.items():
        # Alter existing local databases without replacing their saved runs.
        existing = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
        for name, definition in columns_to_add.items():
            if name not in existing:
                connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
