"""Smoke and integration tests for the command-line interface."""

import json
from pathlib import Path

from refund_agent.cli import build_parser, main


def test_parser_accepts_start_command() -> None:
    """The start command accepts the request identifier required by the workflow."""

    arguments = build_parser().parse_args(["start", "--request-id", "REQ-1001"])

    assert arguments.command == "start"
    assert arguments.request_id == "REQ-1001"


def test_running_without_a_command_prints_help(capsys) -> None:
    """Running the CLI without a command displays help and succeeds."""

    assert main([]) == 0
    assert "usage:" in capsys.readouterr().out


def test_cli_can_start_and_inspect_a_run(tmp_path: Path, capsys) -> None:
    """The first CLI slice persists a run and reads it back."""

    database = tmp_path / "runs.sqlite3"
    assert main(["--db", str(database), "start", "--request-id", "REQ-1001"]) == 0
    run_id = json.loads(capsys.readouterr().out)["run"]["run_id"]

    assert main(["--db", str(database), "inspect", run_id]) == 0
    snapshot = json.loads(capsys.readouterr().out)
    assert snapshot["run"]["status"] == "running"
    assert snapshot["steps"][0]["status"] == "running"
