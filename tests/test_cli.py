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
    """The CLI persists a run and reads it back."""

    database = tmp_path / "runs.sqlite3"
    assert main(["--db", str(database), "start", "--request-id", "REQ-1001"]) == 0
    start_output = json.loads(capsys.readouterr().out)
    run_id = start_output["run_id"]
    assert set(start_output) == {"run_id"}

    assert main(["--db", str(database), "inspect", run_id]) == 0
    snapshot = json.loads(capsys.readouterr().out)
    assert snapshot["run"]["status"] == "paused"
    assert snapshot["run"]["pause_reason"] == "approval"
    assert snapshot["steps"][0]["status"] == "completed"
    context = snapshot["steps"][0]["result"]
    assert context["support_request"]["order_id"] == "ORD-1001"
    assert context["order"]["currency"] == "USD"
    assert context["refund_history"] == {"refunds": []}
    assert snapshot["steps"][1]["result"]["eligible"] is True
    assert snapshot["steps"][2]["status"] == "paused"

    assert main(["--db", str(database), "approve", run_id, "--decision", "reject"]) == 0
    rejected = json.loads(capsys.readouterr().out)
    assert rejected["status"] == "completed"
    assert rejected["business_outcome"] == "rejected"


def test_cli_can_approve_resume_and_trace(tmp_path: Path, capsys) -> None:
    """The command set can complete the happy path across separate invocations."""

    database = tmp_path / "runs.sqlite3"
    assert main(["--db", str(database), "start", "--request-id", "REQ-1001"]) == 0
    run_id = json.loads(capsys.readouterr().out)["run_id"]

    assert main(["--db", str(database), "approve", run_id, "--decision", "approve"]) == 0
    approved = json.loads(capsys.readouterr().out)
    assert approved["pause_reason"] == "provider_confirmation"

    assert main(["--db", str(database), "resume", run_id, "--event", "refund.confirmed"]) == 0
    completed = json.loads(capsys.readouterr().out)
    assert completed["business_outcome"] == "refunded"

    assert main(["--db", str(database), "trace", run_id]) == 0
    trace = json.loads(capsys.readouterr().out)
    assert any(event["event"] == "run_completed" for event in trace)
