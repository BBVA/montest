# Copyright 2026 Banco Bilbao Vizcaya Argentaria, S.A.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from montest.cli import main

_FIXTURE = Path(__file__).parent / "fixtures" / "reports" / "sprt.jsonl"


def test_report_command_writes_html_and_prints_output_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "nested" / "report.html"

    assert main(["report", str(_FIXTURE), "--output", str(output)]) == 0

    captured = capsys.readouterr()
    assert captured.out == f"{output}\n"
    assert captured.err == ""
    assert output.is_file()


def test_report_command_rejects_invalid_recording_without_creating_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "bad.jsonl"
    source.write_text('{"type":"run_start"}\n', encoding="utf-8")
    output = tmp_path / "not-created" / "report.html"

    assert main(["report", str(source), "-o", str(output)]) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Invalid recording" in captured.err
    assert not output.exists()
    assert not output.parent.exists()


def test_report_command_rejects_existing_output_without_modifying_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "input.jsonl"
    source.write_text(_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    output = tmp_path / "report.html"
    output.write_text("existing output", encoding="utf-8")

    assert main(["report", str(source), "-o", str(output)]) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err
    assert source.read_text(encoding="utf-8") == _FIXTURE.read_text(encoding="utf-8")
    assert output.read_text(encoding="utf-8") == "existing output"


def test_report_command_rejects_output_equal_to_input(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "input.jsonl"
    original = _FIXTURE.read_text(encoding="utf-8")
    source.write_text(original, encoding="utf-8")

    assert main(["report", str(source), "-o", str(source)]) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err
    assert source.read_text(encoding="utf-8") == original


def test_module_command_runs_from_an_arbitrary_working_directory(
    tmp_path: Path,
) -> None:
    output = tmp_path / "report.html"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "montest",
            "report",
            str(_FIXTURE),
            "-o",
            str(output),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == f"{output}\n"
    assert completed.stderr == ""
    assert output.is_file()
