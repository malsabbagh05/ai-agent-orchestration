"""SQLite schema for the first persistence slice."""

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    status TEXT NOT NULL,
    business_outcome TEXT,
    pause_reason TEXT,
    pause_data TEXT NOT NULL DEFAULT '{}',
    input_data TEXT NOT NULL,
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
    started_at TEXT,
    completed_at TEXT,
    PRIMARY KEY (run_id, step_number)
);
"""
