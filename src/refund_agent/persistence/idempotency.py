"""Durable records that make side-effect retries safe."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from ..domain.records import utc_now


class IdempotencyStore:
    """Store one result for each stable action key."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def get(self, key: str) -> dict[str, Any] | None:
        """Return the existing action result, if one has been recorded."""

        row = self.connection.execute(
            "SELECT result FROM idempotency WHERE idempotency_key = ?", (key,)
        ).fetchone()
        return json.loads(row["result"]) if row else None

    def record(self, *, key: str, action: str, result: dict[str, Any]) -> dict[str, Any]:
        """Insert an action result once and return the durable result."""

        with self.connection:
            self.connection.execute(
                """
                INSERT OR IGNORE INTO idempotency (idempotency_key, action, result, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (key, action, json.dumps(result), utc_now()),
            )
        stored = self.get(key)
        assert stored is not None
        return stored
