# Copyright 2026 Banco Bilbao Vizcaya Argentaria, S.A.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest

from montest import AllOf, AnyOf, Decision, ObservationResult, sprt
from montest._report import RecordingError, read_recording, render_report
from montest.pytest import cached_samples, stochastic
from tests.conftest import StopAfterN

_FIXTURES = Path(__file__).parent / "fixtures" / "reports"
_START = (
    '{"type":"run_start","schema_version":1,'
    '"run_id":"00000000000000000000000000000000","metadata":{}}\n'
)


class _FlagsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.flags: str | None = None
        self._in_flags = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._in_flags = (
            tag == "script" and dict(attrs).get("type") == "application/json"
        )

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._in_flags = False

    def handle_data(self, data: str) -> None:
        if self._in_flags:
            self.flags = (self.flags or "") + data


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def _events(path: Path) -> list[dict[str, Any]]:
    return read_recording(path)


def test_shared_fixture_behavior_is_preserved() -> None:
    sprt_events = _events(_FIXTURES / "sprt.jsonl")
    assert [event["raw"] for event in sprt_events[1:3]] == ["first", "second"]
    assert sprt_events[2]["result"]["cumulative_llr"] == 3.0
    assert sprt_events[-1]["decision"] == "accept_h1"

    incomplete_events = _events(_FIXTURES / "incomplete.jsonl")
    assert incomplete_events[-1]["type"] == "sample"
    assert incomplete_events[-1]["result"]["decision"] == "continue"

    error_events = _events(_FIXTURES / "terminal-error.jsonl")
    assert error_events[-1]["status"] == "error"
    assert error_events[-1]["decision"] == "accept_h0"
    assert error_events[-1]["error_type"] == "builtins.KeyError"

    nested_events = _events(_FIXTURES / "nested-retry.jsonl")
    assert nested_events[1]["index"] == nested_events[2]["index"] == 0
    assert nested_events[3]["result"]["results"]["skipped"] is None


@pytest.mark.parametrize(
    "name",
    ("sprt", "nested-retry", "incomplete", "terminal-error", "missing-sample"),
)
def test_shared_report_fixtures_are_valid_recordings(name: str) -> None:
    events = _events(_FIXTURES / f"{name}.jsonl")

    assert events[0]["run_id"] == "0" * 32
    assert events[0]["metadata"] == {}


def test_reader_preserves_fixture_evidence_and_large_raw_integer() -> None:
    events = _events(_FIXTURES / "missing-sample.jsonl")

    assert events[2]["index"] == 2
    assert events[2]["raw"] == 9007199254740993
    assert events[-1]["n_observed"] == 3
    retained = events[2]["result"]["terminal_results"]["child"]
    assert retained["index"] == 1
    assert retained["n_observed"] == 2


def test_reader_accepts_blank_lines_and_final_object_without_newline(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path / "recording.jsonl",
        "\n  \n"
        + _START
        + "\n"
        + (
            '{"type":"run_end","status":"incomplete","decision":null,'
            '"n_observed":0,"reason":"no_terminal_decision",'
            '"error_type":null}'
        ),
    )

    assert [event["type"] for event in _events(path)] == [
        "run_start",
        "run_end",
    ]


@pytest.mark.parametrize(
    ("text", "line", "field"),
    (
        (_START + '{"type":"sample"', 2, "$"),
        ('{"type":"run_start","type":"sample"}\n', 1, "$"),
        (
            _START.replace('"schema_version":1', '"schema_version":2'),
            1,
            "$.schema_version",
        ),
        (
            _START
            + (
                '{"type":"sample","index":false,"raw":null,'
                '"observed":null,"metadata":{},"result":{}}\n'
            ),
            2,
            "$.index",
        ),
        (
            _START
            + (
                '{"type":"sample","index":0,"raw":null,'
                '"observed":null,"metadata":[],"result":{}}\n'
            ),
            2,
            "$.metadata",
        ),
        (
            _START
            + (
                '{"type":"sample","index":0,"raw":null,'
                '"observed":null,"metadata":{},"result":{"kind":"sprt",'
                '"index":0,"decision":"continue","cumulative_llr":NaN,'
                '"lower_bound":-2.25,"upper_bound":2.89,"n_observed":1}}\n'
            ),
            2,
            "$",
        ),
        (
            _START
            + (
                '{"type":"run_end","status":"terminal","decision":"continue",'
                '"n_observed":false,"reason":null,"error_type":null}\n'
            ),
            2,
            "$.n_observed",
        ),
        (
            _START
            + (
                '{"type":"run_end","status":"terminal","decision":"accept_h1",'
                '"n_observed":0,"reason":null,"error_type":null}\n'
            )
            + (
                '{"type":"sample","index":0,"raw":null,'
                '"observed":null,"metadata":{},"result":{}}\n'
            ),
            3,
            "$.type",
        ),
        ('{"type":"sample","index":0}\n', 1, "$.type"),
    ),
)
def test_reader_rejects_invalid_jsonl_with_physical_location(
    tmp_path: Path, text: str, line: int, field: str
) -> None:
    expected = rf"^Invalid recording at line {line}, {re.escape(field)}:"
    with pytest.raises(RecordingError, match=expected):
        _events(_write(tmp_path / "bad.jsonl", text))


def test_reader_rejects_empty_recording(tmp_path: Path) -> None:
    with pytest.raises(RecordingError, match=r"line 1, \$"):
        _events(_write(tmp_path / "empty.jsonl", " \n\t\n"))


def test_reader_accepts_start_only_custom_and_inconclusive_results(
    tmp_path: Path,
) -> None:
    start_only = _write(tmp_path / "start.jsonl", _START)
    assert _events(start_only)[0]["type"] == "run_start"

    custom = _write(
        tmp_path / "custom.jsonl",
        _START
        + (
            '{"type":"sample","index":0,"raw":{"id":1},'
            '"observed":["custom"],"metadata":{},"result":'
            '{"kind":"observation","index":0,"decision":"inconclusive"}}\n'
        )
        + (
            '{"type":"run_end","status":"terminal","decision":"inconclusive",'
            '"n_observed":1,"reason":null,"error_type":null}\n'
        ),
    )
    assert _events(custom)[1]["result"]["kind"] == "observation"


def test_rendered_flags_round_trip_exact_event_json_and_safe_text() -> None:
    events = _events(_FIXTURES / "sprt.jsonl")
    events[0]["metadata"] = {"unsafe": "</ScRiPt><b>& snowman ☃"}
    events[1]["raw"] = "</script><img src=x onerror=sentinel()>"
    document = render_report(events)
    parser = _FlagsParser()
    parser.feed(document)

    assert parser.flags is not None
    flags = json.loads(parser.flags)
    assert flags["events"] == events
    assert flags["event_json"] == [
        json.dumps(event, indent=2, allow_nan=False, ensure_ascii=False)
        for event in events
    ]
    assert "</script><img" not in document.lower()


def test_reader_handles_real_producer_retry_local_count_divergence(
    tmp_path: Path,
) -> None:
    calls = 0

    def llr(_: int) -> float:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise LookupError("retry")
        return 3.0

    path = tmp_path / "retry.jsonl"
    with stochastic(cached_samples(lambda: 1), sprt(llr=llr), record_to=path) as run:
        next(run)
        with pytest.raises(LookupError):
            run.observe(1)
        result = run.observe(1)

    events = _events(path)
    assert [event["type"] for event in events] == [
        "run_start",
        "observation_error",
        "sample",
        "run_end",
    ]
    assert events[1]["index"] == events[2]["index"] == result.index == 0
    assert events[2]["result"]["n_observed"] == 2
    assert events[-1]["n_observed"] == 1


def test_reader_accepts_real_producer_nested_composite(tmp_path: Path) -> None:
    path = tmp_path / "nested.jsonl"
    criterion = AllOf(
        {
            "inner": AnyOf(
                {
                    "fast": StopAfterN(1, decision=Decision.ACCEPT_H1),
                    "skipped": StopAfterN(2),
                }
            )
        }
    )
    with stochastic(cached_samples(lambda: "raw"), criterion, record_to=path) as run:
        run.observe(next(run))

    events = _events(path)
    inner = events[1]["result"]["results"]["inner"]
    assert inner["results"]["skipped"] is None
    assert inner["terminal_results"]["fast"]["index"] == 0


class _FailOnce:
    def __init__(self) -> None:
        self.calls = 0

    def observe(self, sample: object, *, index: int) -> ObservationResult[object]:
        self.calls += 1
        if self.calls == 1:
            raise LookupError("partial composite mutation")
        return ObservationResult(sample, index, Decision.ACCEPT_H1)

    def reset(self) -> None:
        self.calls = 0


def test_reader_handles_retained_evidence_after_partial_composite_mutation(
    tmp_path: Path,
) -> None:
    path = tmp_path / "partial.jsonl"
    criterion = AllOf(
        {
            "quick": StopAfterN(1, decision=Decision.ACCEPT_H0),
            "retry": _FailOnce(),
        }
    )
    with stochastic(cached_samples(lambda: "raw"), criterion, record_to=path) as run:
        next(run)
        with pytest.raises(LookupError):
            run.observe("observation")
        run.observe("observation")

    events = _events(path)
    root = events[2]["result"]
    assert root["results"]["quick"] is None
    assert root["terminal_results"]["quick"]["decision"] == "accept_h0"
    assert root["terminal_results"]["quick"]["index"] == 0


def test_reader_accepts_producer_inconclusive_sprt(tmp_path: Path) -> None:
    path = tmp_path / "inconclusive.jsonl"
    with stochastic(
        cached_samples(lambda: "raw"),
        sprt(llr=lambda _: 0.0, max_samples=1),
        record_to=path,
    ) as run:
        run.observe(next(run))
    events = read_recording(path)
    assert events[1]["result"]["decision"] == "inconclusive"
    assert events[1]["result"]["cumulative_llr"] == 0.0
    assert events[-1]["status"] == "terminal"
    assert events[-1]["decision"] == "inconclusive"


@pytest.mark.parametrize(
    "mutation",
    [
        "second_start",
        "second_end",
        "repeated_sample",
        "decreasing_attempt",
        "null_terminal_child",
        "boolean_result_count",
        "unknown_decision",
        "missing_raw",
        "terminal_without_decision",
        "error_without_type",
    ],
)
def test_reader_rejects_invalid_evidence_contracts(
    tmp_path: Path, mutation: str
) -> None:
    events = _events(_FIXTURES / "nested-retry.jsonl")
    if mutation == "second_start":
        events.insert(1, events[0])
    elif mutation == "second_end":
        events.append(events[-1])
    elif mutation == "repeated_sample":
        events.insert(3, events[2])
    elif mutation == "decreasing_attempt":
        events[3]["index"] = 2
        events.insert(4, events[1])
    elif mutation == "null_terminal_child":
        events[3]["result"]["terminal_results"]["nested"] = None
    elif mutation == "boolean_result_count":
        events[2]["result"]["n_total"] = True
    elif mutation == "unknown_decision":
        events[2]["result"]["decision"] = "pass"
    elif mutation == "missing_raw":
        del events[2]["raw"]
    elif mutation == "terminal_without_decision":
        events[-1]["decision"] = None
    elif mutation == "error_without_type":
        events[-1]["status"] = "error"
    text = "\n".join(json.dumps(event) for event in events)
    with pytest.raises(RecordingError):
        read_recording(_write(tmp_path / "invalid.jsonl", text))


@pytest.mark.parametrize("number", ["Infinity", "-Infinity", "1e999"])
def test_reader_rejects_nonfinite_arbitrary_metadata(
    tmp_path: Path, number: str
) -> None:
    text = _START.replace('"metadata":{}', f'"metadata":{{"value":{number}}}')
    with pytest.raises(RecordingError, match="non-finite"):
        read_recording(_write(tmp_path / "nonfinite.jsonl", text))
