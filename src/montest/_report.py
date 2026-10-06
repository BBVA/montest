"""Read recorded evidence and render a standalone run report."""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from importlib.resources import files
from pathlib import Path
from string import Template
from typing import cast

from montest._recording import JSONValue


class RecordingError(ValueError):
    """A recording is not a supported, well-formed run."""


_DECISIONS = {"continue", "accept_h0", "accept_h1", "inconclusive"}


def _fail(line: int, field: str, reason: str) -> None:
    raise RecordingError(f"Invalid recording at line {line}, {field}: {reason}.")


def _field(obj: dict[str, JSONValue], key: str, line: int, path: str) -> JSONValue:
    if key not in obj:
        _fail(line, f"{path}.{key}", "missing required field")
    return obj[key]


def _object(value: JSONValue, line: int, path: str) -> dict[str, JSONValue]:
    if not isinstance(value, dict):
        _fail(line, path, "expected object")
    return cast(dict[str, JSONValue], value)


def _integer(
    value: JSONValue, line: int, path: str, *, nonnegative: bool = False
) -> int:
    if type(value) is not int or (nonnegative and value < 0):
        _fail(
            line,
            path,
            "expected nonnegative integer" if nonnegative else "expected integer",
        )
    return cast(int, value)


def _string(value: JSONValue, line: int, path: str) -> str:
    if not isinstance(value, str):
        _fail(line, path, "expected string")
    return cast(str, value)


def _choice(value: JSONValue, choices: set[str], line: int, path: str) -> str:
    result = _string(value, line, path)
    if result not in choices:
        _fail(line, path, "unknown value")
    return result


def _result(value: JSONValue, line: int, path: str) -> None:
    obj = _object(value, line, path)
    kind = _choice(
        _field(obj, "kind", line, path),
        {"observation", "sprt", "composite"},
        line,
        f"{path}.kind",
    )
    _integer(_field(obj, "index", line, path), line, f"{path}.index")
    _choice(_field(obj, "decision", line, path), _DECISIONS, line, f"{path}.decision")
    if kind == "sprt":
        for key in ("cumulative_llr", "lower_bound", "upper_bound"):
            number = _field(obj, key, line, path)
            if type(number) not in (int, float) or (
                isinstance(number, float) and not math.isfinite(number)
            ):
                _fail(line, f"{path}.{key}", "expected finite number")
        _integer(_field(obj, "n_observed", line, path), line, f"{path}.n_observed")
    elif kind == "composite":
        for key in ("n_decided", "n_total"):
            _integer(_field(obj, key, line, path), line, f"{path}.{key}")
        for key in ("results", "terminal_results"):
            children = _object(_field(obj, key, line, path), line, f"{path}.{key}")
            for name, child in children.items():
                if child is None and key == "results":
                    continue
                _result(child, line, f"{path}.{key}[{json.dumps(name)}]")


def _end(obj: dict[str, JSONValue], line: int) -> None:
    status = _choice(
        _field(obj, "status", line, "$"),
        {"terminal", "incomplete", "error"},
        line,
        "$.status",
    )
    _integer(
        _field(obj, "n_observed", line, "$"), line, "$.n_observed", nonnegative=True
    )
    decision = _field(obj, "decision", line, "$")
    if decision is not None:
        _choice(decision, _DECISIONS - {"continue"}, line, "$.decision")
    reason = _field(obj, "reason", line, "$")
    error = _field(obj, "error_type", line, "$")
    if status == "terminal":
        if decision is None:
            _fail(line, "$.decision", "terminal status requires a terminal decision")
        if reason is not None or error is not None:
            _fail(line, "$", "terminal status requires null reason and error_type")
    elif status == "incomplete":
        _choice(reason, {"unobserved_sample", "no_terminal_decision"}, line, "$.reason")
        if error is not None:
            _fail(line, "$.error_type", "incomplete status requires null error_type")
    else:
        _string(error, line, "$.error_type")
        if reason is not None:
            _fail(line, "$.reason", "error status requires null reason")


def read_recording(path: Path) -> list[dict[str, JSONValue]]:
    """Validate version-1 JSONL without inventing missing evidence."""
    events: list[dict[str, JSONValue]] = []
    ended = False
    last_attempt = -1
    last_sample = -1
    with path.open(encoding="utf-8") as source:
        for line, text in enumerate(source, 1):
            if not text.strip():
                continue

            def pairs(
                items: list[tuple[str, JSONValue]], line: int = line
            ) -> dict[str, JSONValue]:
                obj: dict[str, JSONValue] = {}
                for key, value in items:
                    if key in obj:
                        _fail(line, "$", f"duplicate object key {json.dumps(key)}")
                    obj[key] = value
                return obj

            def constant(value: str, line: int = line) -> JSONValue:
                _fail(line, "$", f"non-finite number {value}")
                return None

            def number(value: str, line: int = line) -> float:
                parsed = float(value)
                if not math.isfinite(parsed):
                    _fail(line, "$", "non-finite number")
                return parsed

            try:
                value = json.loads(
                    text,
                    object_pairs_hook=pairs,
                    parse_constant=constant,
                    parse_float=number,
                )
            except json.JSONDecodeError as error:
                _fail(line, "$", f"malformed JSON ({error.msg})")
            obj = _object(value, line, "$")
            event_type = _string(_field(obj, "type", line, "$"), line, "$.type")
            if ended:
                _fail(line, "$.type", "event after run_end")
            if not events:
                if event_type != "run_start":
                    _fail(line, "$.type", "first event must be run_start")
                version = _integer(
                    _field(obj, "schema_version", line, "$"), line, "$.schema_version"
                )
                if version != 1:
                    _fail(line, "$.schema_version", "unsupported schema version")
                _string(_field(obj, "run_id", line, "$"), line, "$.run_id")
                _object(_field(obj, "metadata", line, "$"), line, "$.metadata")
            elif event_type in ("sample", "observation_error"):
                index = _integer(
                    _field(obj, "index", line, "$"), line, "$.index", nonnegative=True
                )
                if index < last_attempt:
                    _fail(line, "$.index", "attempt indices must not decrease")
                last_attempt = index
                for key in ("raw", "observed"):
                    _field(obj, key, line, "$")
                _object(_field(obj, "metadata", line, "$"), line, "$.metadata")
                if event_type == "sample":
                    if index <= last_sample:
                        _fail(line, "$.index", "sample indices must increase")
                    last_sample = index
                    _result(_field(obj, "result", line, "$"), line, "$.result")
                else:
                    _string(_field(obj, "error_type", line, "$"), line, "$.error_type")
            elif event_type == "run_end":
                _end(obj, line)
                ended = True
            else:
                _fail(line, "$.type", "unexpected event type")
            events.append(obj)
    if not events:
        _fail(1, "$", "empty recording")
    return events


def render_report(events: Sequence[dict[str, JSONValue]]) -> str:
    """Embed original evidence and packaged Elm assets in one offline document."""
    assets = files("montest").joinpath("_assets")
    template = Template(assets.joinpath("report.html").read_text(encoding="utf-8"))
    flags = {
        "events": list(events),
        "event_json": [
            json.dumps(event, indent=2, allow_nan=False, ensure_ascii=False)
            for event in events
        ],
    }
    payload = json.dumps(flags, allow_nan=False, ensure_ascii=True)
    payload = (
        payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    )
    return template.substitute(
        css=assets.joinpath("viewer.css").read_text(encoding="utf-8"),
        javascript=assets.joinpath("viewer.js").read_text(encoding="utf-8"),
        payload=payload,
    )
