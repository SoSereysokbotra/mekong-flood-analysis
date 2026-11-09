"""Fast unit tests for mfi CLI commands (no network, no data, no torch)."""
from __future__ import annotations

import pytest

from mfi.check import CheckError
from mfi.cli import build_parser, main


def test_cli_help(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "check" in captured.out
    assert "report" in captured.out
    assert "districts" in captured.out


def test_cli_subcommand_help(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["check", "--help"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "--date" in captured.out
    assert "--gap" in captured.out
    assert "--years" in captured.out
    assert "--province" in captured.out
    assert "--track" in captured.out


def test_cli_check_defaults(monkeypatch):
    calls = []
    monkeypatch.setattr("mfi.cli.check_flood", lambda **kwargs: calls.append(kwargs))
    main(["check"])
    assert len(calls) == 1
    assert calls[0] == {
        "date": None,
        "gap": 18,
        "years": 3,
        "province": None,
        "track": None,
    }


def test_cli_check_arguments(monkeypatch):
    calls = []
    monkeypatch.setattr("mfi.cli.check_flood", lambda **kwargs: calls.append(kwargs))
    main([
        "check",
        "--date", "2026-9-29",
        "--gap", "12",
        "--years", "1",
        "--province", "Battambang",
        "--track", "99a",
    ])
    assert len(calls) == 1
    assert calls[0] == {
        "date": "2026-9-29",
        "gap": 12,
        "years": 1,
        "province": "Battambang",
        "track": "99a",
    }


def test_cli_report(monkeypatch):
    called = []
    monkeypatch.setattr("mfi.cli.build_report", lambda: called.append(True))
    main(["report"])
    assert called == [True]


def test_cli_districts(monkeypatch):
    called = []
    monkeypatch.setattr("mfi.cli.run_district_areas", lambda: called.append(True))
    main(["districts"])
    assert called == [True]


def test_cli_check_error_exits_1(monkeypatch, capsys):
    def fake_check(**kwargs):
        raise CheckError("test check failure")

    monkeypatch.setattr("mfi.cli.check_flood", fake_check)
    with pytest.raises(SystemExit) as exc:
        main(["check"])
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "test check failure" in captured.err


def test_build_parser():
    parser = build_parser()
    args = parser.parse_args(["check", "--date", "2026-10-15"])
    assert args.command == "check"
    assert args.date == "2026-10-15"
