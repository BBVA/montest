"""Convert one recorded Montest run into a standalone HTML report."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from montest._report import RecordingError, read_recording, render_report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    report = commands.add_parser("report", help="convert a JSONL run to offline HTML")
    report.add_argument("input", type=Path, metavar="INPUT")
    report.add_argument("-o", "--output", type=Path, required=True, metavar="OUTPUT")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Write a report without replacing an existing output file."""
    arguments = _parser().parse_args(argv)
    try:
        events = read_recording(arguments.input)
        document = render_report(events)
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        with arguments.output.open("x", encoding="utf-8") as output:
            output.write(document)
    except (RecordingError, OSError, UnicodeError) as error:
        print(f"montest: {error}", file=sys.stderr)
        return 1
    print(arguments.output)
    return 0
