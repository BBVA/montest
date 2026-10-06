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

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from montest import (
    ANY_OF_DECISION_MONOID,
    AllOf,
    AnyOf,
    Decision,
    ObservationResult,
    sprt,
)
from montest._recording import RunWriter
from montest.pytest import cached_samples, stochastic
from tests.conftest import StopAfterN


def _events(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines()]


@dataclass(frozen=True, slots=True)
class RawSpin:
    number: int


def test_records_raw_observation_sprt_evidence_and_independent_replays(
    tmp_path: Path,
) -> None:
    generated = 0
    values = iter((RawSpin(3), RawSpin(7)))

    def generate() -> RawSpin:
        nonlocal generated
        generated += 1
        return next(values)

    samples = cached_samples(generate)
    files = [tmp_path / "first.jsonl", tmp_path / "second.jsonl"]
    for path in files:
        with stochastic(
            samples,
            sprt(llr=lambda _: 1.5),
            record_to=path,
            run_metadata={"scenario": "replay"},
            serialize_sample=lambda spin: {"number": spin.number},
        ) as run:
            for spin in run:
                run.observe(spin.number % 5, metadata={"wheel_rpm": 25.5})
        assert run.result.decision is Decision.ACCEPT_H1

    assert generated == 2
    first, second = (_events(path) for path in files)
    assert first[0]["type"] == second[0]["type"] == "run_start"
    assert first[0]["schema_version"] == 1
    assert first[0]["metadata"] == {"scenario": "replay"}
    assert len(first[0]["run_id"]) == 32
    assert first[0]["run_id"] != second[0]["run_id"]
    assert [event["raw"] for event in first[1:3]] == [
        {"number": 3}, {"number": 7}
    ]
    assert [event["observed"] for event in first[1:3]] == [3, 2]
    assert [event["index"] for event in first[1:3]] == [0, 1]
    assert all(event["metadata"] == {"wheel_rpm": 25.5} for event in first[1:3])
    assert first[1]["result"] == {
        "kind": "sprt",
        "index": 0,
        "decision": "continue",
        "cumulative_llr": 1.5,
        "lower_bound": pytest.approx(math.log(0.10 / 0.95)),
        "upper_bound": pytest.approx(math.log(0.90 / 0.05)),
        "n_observed": 1,
    }
    assert first[2]["result"]["cumulative_llr"] == 3.0
    assert first[2]["result"]["decision"] == "accept_h1"
    assert first[2]["result"]["n_observed"] == 2
    assert first[3] == {
        "type": "run_end",
        "status": "terminal",
        "decision": "accept_h1",
        "n_observed": 2,
        "reason": None,
        "error_type": None,
    }
    assert first[1:] == second[1:]


def test_nested_composite_keeps_skipped_children_and_terminal_evidence(
    tmp_path: Path,
) -> None:
    nested = AllOf(
        {
            "quick": StopAfterN(1, decision=Decision.ACCEPT_H0),
            "slow": StopAfterN(2, decision=Decision.ACCEPT_H1),
        },
        resolve=ANY_OF_DECISION_MONOID.resolve,
    )
    criterion = AnyOf({"nested": nested, "skipped": StopAfterN(3)})
    path = tmp_path / "composite.jsonl"
    with stochastic(cached_samples(lambda: "raw"), criterion, record_to=path) as run:
        for raw in run:
            run.observe(raw)

    records = _events(path)
    assert [event["type"] for event in records] == [
        "run_start", "sample", "sample", "run_end"
    ]
    root = records[2]["result"]
    assert root["kind"] == "composite"
    assert root["index"] == 1
    assert root["decision"] == "accept_h1"
    assert root["n_decided"] == 1
    assert root["n_total"] == 2
    assert root["results"]["skipped"] is None
    assert set(root["terminal_results"]) == {"nested"}
    child = root["results"]["nested"]
    assert child == root["terminal_results"]["nested"]
    assert child["kind"] == "composite"
    assert child["results"]["quick"] is None
    assert child["results"]["slow"]["decision"] == "accept_h1"
    assert set(child["terminal_results"]) == {"quick", "slow"}
    assert root["decision"] == records[-1]["decision"]


class RetryCriterion:
    def __init__(self) -> None:
        self.calls = 0

    def observe(self, sample: int, *, index: int) -> ObservationResult[int]:
        self.calls += 1
        if self.calls == 1:
            raise LookupError("temporary failure")
        return ObservationResult(sample, index, Decision.ACCEPT_H0)

    def reset(self) -> None:
        self.calls = 0


def test_criterion_failure_retains_pending_raw_for_retry(tmp_path: Path) -> None:
    path = tmp_path / "retry.jsonl"
    criterion = RetryCriterion()
    with stochastic(cached_samples(lambda: None), criterion, record_to=path) as run:
        assert next(run) is None
        with pytest.raises(LookupError, match="temporary failure"):
            run.observe(7)
        with pytest.raises(RuntimeError, match="must be observed"):
            next(run)
        assert run.observe(7).decision is Decision.ACCEPT_H0

    assert criterion.calls == 2
    records = _events(path)
    assert [record["type"] for record in records] == [
        "run_start", "observation_error", "sample", "run_end"
    ]
    assert records[1]["error_type"] == "builtins.LookupError"
    assert records[1]["index"] == records[2]["index"] == 0
    assert records[1]["raw"] is records[2]["raw"] is None
    assert records[-1]["status"] == "terminal"
    assert records[-1]["n_observed"] == 1


@pytest.mark.parametrize(
    ("action", "reason", "count"),
    [
        ("pending", "unobserved_sample", 0),
        ("nonterminal", "no_terminal_decision", 1),
    ],
)
def test_clean_incomplete_exit_preserves_lifecycle_error(
    tmp_path: Path, action: str, reason: str, count: int
) -> None:
    path = tmp_path / "incomplete.jsonl"
    run = stochastic(cached_samples(lambda: "raw"), StopAfterN(2), record_to=path)
    with pytest.raises(RuntimeError) as caught:
        with run:
            raw = next(run)
            if action == "nonterminal":
                run.observe(raw)

    assert str(caught.value) == (
        "Stochastic run exited with an unobserved sample."
        if action == "pending"
        else "Stochastic run exited before the criterion reached a terminal decision."
    )
    assert _events(path)[-1] == {
        "type": "run_end", "status": "incomplete", "decision": None,
        "n_observed": count, "reason": reason, "error_type": None,
    }


def test_body_exception_has_priority_over_pending_sample(tmp_path: Path) -> None:
    path = tmp_path / "body.jsonl"
    error = KeyError("body")
    run = stochastic(cached_samples(lambda: 1), StopAfterN(1), record_to=path)
    with pytest.raises(KeyError) as caught:
        with run:
            next(run)
            raise error

    assert caught.value is error
    assert _events(path)[-1] == {
        "type": "run_end", "status": "error", "decision": None,
        "n_observed": 0, "reason": None, "error_type": "builtins.KeyError",
    }


def test_invalid_input_does_not_reach_criterion(tmp_path: Path) -> None:
    path = tmp_path / "invalid.jsonl"
    criterion = RetryCriterion()
    with stochastic(cached_samples(lambda: "raw"), criterion, record_to=path) as run:
        assert next(run) == "raw"
        with pytest.raises(ValueError):
            run.observe(7, metadata={"speed": math.inf})
        with pytest.raises(TypeError):
            run.observe(7, metadata={1: "bad"})  # type: ignore[dict-item]
        assert criterion.calls == 0
        with pytest.raises(LookupError):
            run.observe(7)
        run.observe(7)

    assert [event["type"] for event in _events(path)] == [
        "run_start", "observation_error", "sample", "run_end"
    ]


def test_existing_file_and_invalid_parent_fail_before_generation(
    tmp_path: Path,
) -> None:
    existing = tmp_path / "existing.jsonl"
    existing.write_text("untouched")
    parent_file = tmp_path / "parent"
    parent_file.write_text("parent intact")
    generated = 0

    def generate() -> int:
        nonlocal generated
        generated += 1
        return 4

    for path, expected_error in (
        (existing, FileExistsError),
        (parent_file / "run.jsonl", OSError),
    ):
        run = stochastic(cached_samples(generate), StopAfterN(1), record_to=path)
        with pytest.raises(expected_error):
            with run:
                next(run)
        assert run.n_observed == 0

    assert generated == 0
    assert existing.read_text() == "untouched"
    assert parent_file.read_text() == "parent intact"


def test_recording_options_require_a_path_and_metadata_requires_a_writer() -> None:
    samples = cached_samples(lambda: 1)
    with pytest.raises(ValueError, match="recording options require record_to"):
        stochastic(samples, StopAfterN(1), run_metadata={})
    with stochastic(samples, StopAfterN(1)) as run:
        next(run)
        with pytest.raises(ValueError, match="metadata requires record_to"):
            run.observe(1, metadata={})
        run.observe(1)


def test_write_failure_keeps_criterion_state_and_body_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recording_error = OSError("disk failure")

    def fail_write(self: RunWriter, event: dict[str, Any]) -> None:
        raise recording_error

    monkeypatch.setattr(RunWriter, "write", fail_write)
    path = tmp_path / "failure.jsonl"
    run = stochastic(cached_samples(lambda: 1), StopAfterN(1), record_to=path)
    with pytest.raises(OSError) as caught:
        with run:
            run.observe(next(run))

    assert caught.value is recording_error
    assert run.n_observed == 1
    assert run.result.decision is Decision.ACCEPT_H1
    assert [event["type"] for event in _events(path)] == ["run_start"]

    body_error = LookupError("body")
    second = stochastic(
        cached_samples(lambda: 1),
        StopAfterN(1),
        record_to=tmp_path / "body-failure.jsonl",
    )
    with pytest.raises(LookupError) as body_caught:
        with second:
            next(second)
            raise body_error
    assert body_caught.value is body_error
