"""Smoke tests for the initial command-line interface scaffold."""

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
