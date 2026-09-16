"""SQLite schema for durable workflow state."""

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    status TEXT NOT NULL,
    business_outcome TEXT,
    pause_reason TEXT,
    pause_data TEXT NOT NULL DEFAULT '{}',
    input_data TEXT NOT NULL,
    error_type TEXT,
    error_message TEXT,
    tool_calls INTEGER NOT NULL DEFAULT 0,
    max_steps INTEGER NOT NULL DEFAULT 10,
    max_tool_calls INTEGER NOT NULL DEFAULT 20,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS steps (
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    step_number INTEGER NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    pause_reason TEXT,
    result TEXT,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    tool_name TEXT,
    idempotency_key TEXT,
    error_type TEXT,
    error_message TEXT,
    started_at TEXT,
    completed_at TEXT,
    PRIMARY KEY (run_id, step_number)
);

CREATE TABLE IF NOT EXISTS idempotency (
    idempotency_key TEXT PRIMARY KEY,
    action TEXT NOT NULL,
    result TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trace (
    trace_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    step_number INTEGER,
    step_name TEXT,
    event TEXT NOT NULL,
    status TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    tool_name TEXT,
    pause_reason TEXT,
    retry_attempt INTEGER,
    retry_limit INTEGER,
    error_type TEXT,
    error_message TEXT,
    details TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_trace_run ON trace(run_id, trace_id);
"""
