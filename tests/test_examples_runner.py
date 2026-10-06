# Copyright 2026 Banco Bilbao Vizcaya Argentaria, S.A.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_RUNNER_PATH = _REPOSITORY_ROOT / "examples" / "pytest" / "runner.py"
_EXAMPLE_TESTS = _RUNNER_PATH.parent / "tests"
_LIVE_EXTRA_ERROR = "LLM example requires the 'llm' extra."
_LIVE_CREDENTIAL_ERROR = "LLM example requires GOOGLE_API_KEY or GEMINI_API_KEY."


def _run_runner(tmp_path: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_RUNNER_PATH), *arguments],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )


def _load_runner() -> ModuleType:
    specification = importlib.util.spec_from_file_location(
        "pytest_example_runner", _RUNNER_PATH
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("group", "description"),
    (
        ("coin", "Coin fairness examples."),
        ("dice", "Dice fairness examples."),
        ("roulette", "Roulette fairness examples."),
        ("llm", "Live LLM emoji example."),
        ("offline", "Coin, dice, and roulette examples (no external service)."),
        ("all", "Every example group."),
    ),
)
def test_list_names_every_runner_group(
    tmp_path: Path, group: str, description: str
) -> None:
    completed = _run_runner(tmp_path, "list")

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert f"  {group:<9} {description}" in completed.stdout


@pytest.mark.parametrize(
    ("group", "filename"),
    (
        ("coin", "test_coin_fairness.py"),
        ("dice", "test_dice_fairness.py"),
        ("roulette", "test_roulette_fairness.py"),
    ),
)
def test_individual_offline_groups_collect_from_an_arbitrary_directory(
    tmp_path: Path, group: str, filename: str
) -> None:
    completed = _run_runner(tmp_path, "run", group, "--collect-only", "-q")

    assert completed.returncode == 0, completed.stderr
    assert f"{filename}::" in completed.stdout
    for other_filename in {
        "test_coin_fairness.py",
        "test_dice_fairness.py",
        "test_roulette_fairness.py",
    } - {filename}:
        assert other_filename not in completed.stdout


def test_offline_group_executes_seeded_examples(tmp_path: Path) -> None:
    completed = _run_runner(tmp_path, "run", "offline", "-q")

    assert completed.returncode == 0, completed.stderr
    assert "4 passed" in completed.stdout
    assert "3 xfailed" in completed.stdout


def test_roulette_run_writes_two_evidence_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "records"
    monkeypatch.setenv("MONTEST_RECORD_DIR", str(directory))
    completed = _run_runner(tmp_path, "run", "roulette", "-q")

    assert completed.returncode == 0, completed.stderr
    assert "1 passed" in completed.stdout
    assert "1 xfailed" in completed.stdout
    files = sorted(directory.glob("roulette-*.jsonl"))
    assert len(files) == 2
    red_numbers = {
        1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36
    }
    for path, scenario, decision in zip(
        files, ("fair", "rigged"), ("accept_h0", "accept_h1"), strict=True
    ):
        assert path.name.startswith(f"roulette-{scenario}-")
        records = [json.loads(line) for line in path.read_text().splitlines()]
        assert records[0]["type"] == "run_start"
        assert records[0]["schema_version"] == 1
        assert records[0]["metadata"]["scenario"] == scenario
        assert records[0]["metadata"]["telemetry"] == "simulated"
        assert records[-1]["type"] == "run_end"
        assert records[-1]["status"] == "terminal"
        assert records[-1]["decision"] == decision
        for index, record in enumerate(records[1:-1]):
            assert record["type"] == "sample"
            assert record["index"] == index
            number = record["raw"]["number"]
            assert isinstance(number, int) and 0 <= number <= 36
            color = (
                "green" if number == 0
                else "red" if number in red_numbers
                else "black"
            )
            assert record["observed"] == color
            assert 24 <= record["metadata"]["wheel_rpm"] <= 28
            assert 34 <= record["metadata"]["ball_rpm"] <= 38
            assert 4200 <= record["metadata"]["duration_ms"] <= 6200
            assert set(record["result"]["results"]) == {"red", "black", "green"}
        assert records[-1]["n_observed"] == len(records) - 2


@pytest.mark.parametrize("group", ("llm", "all"))
def test_live_groups_fail_for_missing_extra_before_pytest(
    tmp_path: Path, group: str
) -> None:
    completed = _run_runner(tmp_path, "run", group)

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert completed.stderr == f"{_LIVE_EXTRA_ERROR}\n"


@pytest.mark.parametrize("group", ("llm", "all"))
def test_live_groups_fail_for_missing_credentials_before_pytest(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], group: str
) -> None:
    runner = _load_runner()
    monkeypatch.setattr(runner, "_llm_available", lambda: True)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    def pytest_main_must_not_run(arguments: list[str]) -> int:
        raise AssertionError(f"pytest.main was called with {arguments!r}")

    monkeypatch.setattr(runner.pytest, "main", pytest_main_must_not_run)

    assert runner.main(["run", group]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"{_LIVE_CREDENTIAL_ERROR}\n"


@pytest.mark.parametrize(
    ("group", "filenames"),
    (
        ("coin", ("test_coin_fairness.py",)),
        ("dice", ("test_dice_fairness.py",)),
        ("roulette", ("test_roulette_fairness.py",)),
        (
            "offline",
            (
                "test_coin_fairness.py",
                "test_dice_fairness.py",
                "test_roulette_fairness.py",
            ),
        ),
        ("llm", ("test_llm_emoji.py",)),
        (
            "all",
            (
                "test_coin_fairness.py",
                "test_dice_fairness.py",
                "test_roulette_fairness.py",
                "test_llm_emoji.py",
            ),
        ),
    ),
)
def test_run_forwards_absolute_test_paths_and_trailing_arguments_in_order(
    monkeypatch: pytest.MonkeyPatch, group: str, filenames: tuple[str, ...]
) -> None:
    runner = _load_runner()
    monkeypatch.setattr(runner, "_llm_available", lambda: True)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    forwarded: list[list[str]] = []

    def pytest_main(arguments: list[str]) -> int:
        forwarded.append(arguments)
        return 23

    monkeypatch.setattr(runner.pytest, "main", pytest_main)
    trailing = ["-q", "--maxfail=1"]

    assert runner.main(["run", group, *trailing]) == 23
    assert forwarded == [
        [*(str(_EXAMPLE_TESTS / filename) for filename in filenames), *trailing]
    ]
