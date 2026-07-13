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
