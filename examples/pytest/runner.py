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

"""Run the standalone Montest pytest examples."""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

_TESTS_DIRECTORY = Path(__file__).resolve().parent / "tests"
_SCENARIOS = {
    "coin": (_TESTS_DIRECTORY / "test_coin_fairness.py",),
    "dice": (_TESTS_DIRECTORY / "test_dice_fairness.py",),
    "roulette": (_TESTS_DIRECTORY / "test_roulette_fairness.py",),
    "llm": (_TESTS_DIRECTORY / "test_llm_emoji.py",),
}
_GROUPS = {
    **_SCENARIOS,
    "offline": (
        _SCENARIOS["coin"]
        + _SCENARIOS["dice"]
        + _SCENARIOS["roulette"]
    ),
    "all": (
        _SCENARIOS["coin"]
        + _SCENARIOS["dice"]
        + _SCENARIOS["roulette"]
        + _SCENARIOS["llm"]
    ),
}


def _llm_available() -> bool:
    """Return whether the optional Google Gen AI package is importable."""
    try:
        return importlib.util.find_spec("google.genai") is not None
    except ModuleNotFoundError:
        return False


def _has_llm_credentials() -> bool:
    return bool(os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="list available example groups")
    run = commands.add_parser("run", help="run an example group with pytest")
    run.add_argument("group", choices=tuple(_GROUPS))
    run.add_argument("pytest_args", nargs=argparse.REMAINDER)
    return parser


def _print_groups() -> None:
    print("Available example groups:")
    print("  coin      Coin fairness examples.")
    print("  dice      Dice fairness examples.")
    print("  roulette  Roulette fairness examples.")
    print("  llm       Live LLM emoji example.")
    print("  offline   Coin, dice, and roulette examples (no external service).")
    print("  all       Every example group.")
    print()
    print(
        "The llm and all groups require the 'llm' extra, credentials, network, "
        "and paid API calls."
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run a selected example group and return pytest's exit status."""
    arguments = _parser().parse_args(argv)
    if arguments.command == "list":
        _print_groups()
        return 0

    group = arguments.group
    if group in {"llm", "all"}:
        if not _llm_available():
            print("LLM example requires the 'llm' extra.", file=sys.stderr)
            return 2
        if not _has_llm_credentials():
            print(
                "LLM example requires GOOGLE_API_KEY or GEMINI_API_KEY.",
                file=sys.stderr,
            )
            return 2

    test_paths = [str(path) for path in _GROUPS[group]]
    return pytest.main([*test_paths, *arguments.pytest_args])


if __name__ == "__main__":
    raise SystemExit(main())
