"""Command-line interface for the refund support agent."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence

from .orchestration import Orchestrator
from .persistence import RunStore
from .tools import MockSupportRequestReader


def build_parser() -> argparse.ArgumentParser:
    """Build and return the parser used by the application."""

    parser = argparse.ArgumentParser(
        prog="refund-agent",
        description="Run and inspect durable customer refund workflows.",
    )
    parser.add_argument(
        "--db",
        default=os.environ.get("REFUND_AGENT_DB", "data/runs.sqlite3"),
        help="SQLite database path (default: data/runs.sqlite3).",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )

    commands = parser.add_subparsers(dest="command", metavar="COMMAND")

    start = commands.add_parser("start", help="Start a new refund workflow run.")
    start.add_argument("--request-id", required=True, help="Refund request to process.")

    inspect = commands.add_parser("inspect", help="Show the current state of a run.")
    inspect.add_argument("run_id", help="Run identifier.")

    approve = commands.add_parser("approve", help="Approve or reject a paused refund.")
    approve.add_argument("run_id", help="Run identifier.")
    approve.add_argument(
        "--decision",
        required=True,
        choices=("approve", "reject"),
        help="Approval decision.",
    )

    resume = commands.add_parser("resume", help="Resume a run after an external event.")
    resume.add_argument("run_id", help="Run identifier.")
    resume.add_argument("--event", required=True, help="External event identifier.")

    cancel = commands.add_parser("cancel", help="Cancel a run.")
    cancel.add_argument("run_id", help="Run identifier.")

    trace = commands.add_parser("trace", help="Show the execution trace for a run.")
    trace.add_argument("run_id", help="Run identifier.")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse command-line input and return a process exit code."""

    parser = build_parser()
    arguments = parser.parse_args(argv)

    if arguments.command is None:
        parser.print_help()
        return 0

    if arguments.command not in {"start", "inspect"}:
        parser.error(f"Command '{arguments.command}' is planned for a later step.")

    store = RunStore(arguments.db)
    try:
        orchestrator = Orchestrator(store, MockSupportRequestReader())
        if arguments.command == "start":
            result = orchestrator.start_run(arguments.request_id)
        else:
            result = orchestrator.inspect_run(arguments.run_id)
    except (KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        store.close()

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0
