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

import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass

import pytest

from montest import AllOf, AnyOf, CompositeResult, Decision, ObservationResult
from montest.pytest import CachedSamples, StochasticRun, cached_samples, stochastic
from tests.conftest import StopAfterN


@dataclass(frozen=True, slots=True)
class ScriptedResult(ObservationResult[str]):
    """A distinct result type proving the run preserves criterion result types."""


class ScriptedCriterion:
    def __init__(self, script: list[Decision | BaseException]) -> None:
        self._script = iter(script)
        self.observations: list[tuple[int, int]] = []
        self.reset_calls = 0

    def observe(self, observation: int, *, index: int) -> ScriptedResult:
        self.observations.append((observation, index))
        outcome = next(self._script)
        if isinstance(outcome, BaseException):
            raise outcome
        return ScriptedResult(
            value=f"observation={observation}", index=index, decision=outcome
        )

    def reset(self) -> None:
        self.reset_calls += 1


def _samples(values: list[str]) -> CachedSamples[str]:
    generate = iter(values).__next__
    return cached_samples(generate)


def _exact_message(message: str) -> str:
    return f"^{re.escape(message)}$"


def test_context_body_transforms_raw_samples_and_preserves_typed_results() -> None:
    criterion = ScriptedCriterion([Decision.CONTINUE, Decision.ACCEPT_H0])
    run = stochastic(_samples(["cat", "mouse"]), criterion)
    observed_results: list[ScriptedResult] = []
    raw_samples: list[str] = []

    with run:
        for raw in run:
            raw_samples.append(raw)
            observed_results.append(run.observe(len(raw)))

    assert raw_samples == ["cat", "mouse"]
    assert criterion.observations == [(3, 0), (5, 1)]
    assert all(isinstance(result, ScriptedResult) for result in observed_results)
    assert [result.value for result in observed_results] == [
        "observation=3",
        "observation=5",
    ]
    assert [result.index for result in observed_results] == [0, 1]
    assert run.result is observed_results[-1]
    assert run.n_observed == 2


@pytest.mark.parametrize(
    "decision",
    [Decision.ACCEPT_H0, Decision.ACCEPT_H1, Decision.INCONCLUSIVE],
)
def test_terminal_decisions_match_and_remain_readable_after_exit(
    decision: Decision,
) -> None:
    run = StochasticRun(_samples(["raw"]), StopAfterN(1, decision=decision))

    with run:
        terminal = run.observe(next(run).upper())

    assert terminal.decision is decision
    assert run.result is terminal
    assert run.n_observed == 1
    run.assert_decision(decision)


def test_assert_decision_reports_exact_mismatch_without_traceback() -> None:
    run = stochastic(_samples(["raw"]), ScriptedCriterion([Decision.ACCEPT_H0]))

    with pytest.raises(pytest.fail.Exception) as caught:
        with run:
            result = run.observe(len(next(run)))
            run.assert_decision(Decision.ACCEPT_H1)

    assert str(caught.value) == (
        "Montest stochastic decision mismatch\n"
        "expected: accept_h1\n"
        "actual: accept_h0\n"
        "observations: 1\n"
        f"result: {result!r}"
    )
    assert caught.value.pytrace is False
    assert run.n_observed == 1
    assert run.result is result


def test_assert_decision_rejects_continue_as_an_expected_decision() -> None:
    run = StochasticRun(_samples(["raw"]), StopAfterN(1))

    with pytest.raises(ValueError, match="^expected decision must be terminal$"):
        run.assert_decision(Decision.CONTINUE)


def test_operations_require_an_active_run() -> None:
    run = StochasticRun(_samples(["raw"]), StopAfterN(1))
    operations: list[Callable[[], object]] = [
        lambda: iter(run),
        lambda: next(run),
        lambda: run.observe("derived"),
    ]

    for operation in operations:
        with pytest.raises(
            RuntimeError, match=_exact_message("Stochastic run is not active.")
        ):
            operation()


def test_run_can_be_entered_only_once() -> None:
    run = StochasticRun(_samples(["raw"]), StopAfterN(1))

    with run:
        run.observe(next(run))
        with pytest.raises(
            RuntimeError,
            match=_exact_message("Stochastic run cannot be entered more than once."),
        ):
            run.__enter__()

    with pytest.raises(
        RuntimeError,
        match=_exact_message("Stochastic run cannot be entered more than once."),
    ):
        run.__enter__()


def test_active_run_enforces_one_observation_per_raw_sample() -> None:
    run = StochasticRun(_samples(["first", "second"]), StopAfterN(2))

    with run:
        assert iter(run) is run
        first = next(run)
        with pytest.raises(
            RuntimeError,
            match=_exact_message(
                "Current sample must be observed before requesting another sample."
            ),
        ):
            next(run)

        first_result = run.observe(first)
        assert first_result.decision is Decision.CONTINUE
        with pytest.raises(
            RuntimeError,
            match=_exact_message("No sample is awaiting an observation."),
        ):
            run.observe("duplicate")

        terminal = run.observe(next(run))

    assert terminal.decision is Decision.ACCEPT_H1
    assert run.n_observed == 2


def test_terminal_run_stops_only_while_active_and_rejects_further_observations(
) -> None:
    run = StochasticRun(_samples(["raw"]), StopAfterN(1))

    with run:
        terminal = run.observe(next(run))
        with pytest.raises(StopIteration):
            next(run)
        with pytest.raises(
            RuntimeError,
            match=_exact_message(
                "Stochastic run already reached a terminal decision."
            ),
        ):
            run.observe("another")

    assert run.result is terminal
    with pytest.raises(
        RuntimeError, match=_exact_message("Stochastic run is not active.")
    ):
        next(run)


def test_result_is_unavailable_until_the_criterion_returns_a_terminal_result(
) -> None:
    run = StochasticRun(_samples(["raw"]), StopAfterN(1))

    with pytest.raises(
        RuntimeError,
        match=_exact_message("Stochastic run has not reached a terminal decision."),
    ):
        _ = run.result

    with run:
        with pytest.raises(
            RuntimeError,
            match=_exact_message("Stochastic run has not reached a terminal decision."),
        ):
            _ = run.result
        terminal = run.observe(next(run))

    assert run.result is terminal


@pytest.mark.parametrize(
    ("body", "message", "n_observed"),
    [
        (
            lambda run: next(run),
            "Stochastic run exited with an unobserved sample.",
            0,
        ),
        (
            lambda run: run.observe(next(run)),
            "Stochastic run exited before the criterion reached a terminal decision.",
            1,
        ),
    ],
)
def test_clean_exit_requires_a_terminal_observation_and_leaves_run_inactive(
    body: Callable[[StochasticRun[str, str, ObservationResult[object]]], object],
    message: str,
    n_observed: int,
) -> None:
    run = StochasticRun(_samples(["raw"]), StopAfterN(2))

    with pytest.raises(RuntimeError, match=_exact_message(message)):
        with run:
            body(run)

    assert run.n_observed == n_observed
    exited_operations: list[Callable[[], object]] = [
        lambda: iter(run),
        lambda: next(run),
        lambda: run.observe("derived"),
    ]
    for operation in exited_operations:
        with pytest.raises(
            RuntimeError, match=_exact_message("Stochastic run is not active.")
        ):
            operation()


def test_body_generator_and_criterion_exceptions_are_not_replaced_during_exit() -> None:
    body_error = LookupError("body failure")
    body_run = StochasticRun(_samples(["raw"]), StopAfterN(1))

    with pytest.raises(LookupError) as body_caught:
        with body_run:
            raise body_error

    assert body_caught.value is body_error

    generator_error = OSError("generator failure")

    def generate() -> str:
        raise generator_error

    generator_run = StochasticRun(cached_samples(generate), StopAfterN(1))
    with pytest.raises(OSError) as generator_caught:
        with generator_run:
            next(generator_run)

    assert generator_caught.value is generator_error

    criterion_error = ArithmeticError("criterion failure")
    criterion_run = stochastic(
        _samples(["raw"]), ScriptedCriterion([criterion_error])
    )
    with pytest.raises(ArithmeticError) as criterion_caught:
        with criterion_run:
            criterion_run.observe(len(next(criterion_run)))

    assert criterion_caught.value is criterion_error


def test_criterion_failure_preserves_the_outstanding_sample_for_retry() -> None:
    criterion_error = ArithmeticError("criterion failure")
    criterion = ScriptedCriterion([criterion_error, Decision.ACCEPT_H1])
    run = stochastic(_samples(["raw"]), criterion)

    with run:
        raw = next(run)
        with pytest.raises(ArithmeticError) as caught:
            run.observe(len(raw))

        assert caught.value is criterion_error
        assert run.n_observed == 0
        with pytest.raises(
            RuntimeError,
            match=_exact_message("Stochastic run has not reached a terminal decision."),
        ):
            _ = run.result
        with pytest.raises(
            RuntimeError,
            match=_exact_message(
                "Current sample must be observed before requesting another sample."
            ),
        ):
            next(run)

        terminal = run.observe(len(raw))

    assert criterion.observations == [(3, 0), (3, 0)]
    assert terminal.index == 0
    assert run.n_observed == 1
    assert run.result is terminal


def test_reusing_a_terminal_criterion_requires_a_fresh_criterion() -> None:
    criterion = AnyOf({"only": StopAfterN(1)})
    samples = _samples(["first", "second"])

    with stochastic(samples, criterion) as first_run:
        first_run.observe(next(first_run))

    second_run = stochastic(samples, criterion)
    with pytest.raises(
        RuntimeError,
        match=_exact_message(
            "Criterion already reached a decision; call reset() first."
        ),
    ):
        with second_run:
            second_run.observe(next(second_run))

    assert second_run.n_observed == 0


def test_all_of_preserves_terminal_and_skipped_child_evidence() -> None:
    criterion = AllOf(
        {
            "fast": StopAfterN(1, decision=Decision.ACCEPT_H0),
            "slow": StopAfterN(2, decision=Decision.INCONCLUSIVE),
        }
    )
    run = stochastic(_samples(["3", "4"]), criterion)

    with run:
        results: list[CompositeResult[int]] = []
        for raw in run:
            results.append(run.observe(int(raw)))

    terminal = results[-1]
    assert [result.value for result in results] == [3, 4]
    assert [result.index for result in results] == [0, 1]
    assert terminal.decision is Decision.ACCEPT_H0
    assert terminal.results["fast"] is None
    assert terminal.results["slow"] is terminal.terminal_results["slow"]
    assert {
        key: result.decision for key, result in terminal.terminal_results.items()
    } == {"fast": Decision.ACCEPT_H0, "slow": Decision.INCONCLUSIVE}
    assert terminal.n_decided == 2
    assert terminal.n_total == 2
    assert run.n_observed == 2


def test_any_of_preserves_early_terminal_and_skipped_child_evidence() -> None:
    criterion = AnyOf(
        {
            "prior_h0": StopAfterN(1, decision=Decision.ACCEPT_H0),
            "winner": StopAfterN(2, decision=Decision.ACCEPT_H1),
            "skipped": StopAfterN(3, decision=Decision.ACCEPT_H0),
        }
    )
    run = stochastic(_samples(["2", "5"]), criterion)

    with run:
        results: list[CompositeResult[int]] = []
        for raw in run:
            results.append(run.observe(int(raw)))

    terminal = results[-1]
    assert [result.value for result in results] == [2, 5]
    assert [result.index for result in results] == [0, 1]
    assert terminal.decision is Decision.ACCEPT_H1
    assert terminal.results["prior_h0"] is None
    assert terminal.results["winner"] is terminal.terminal_results["winner"]
    assert terminal.results["skipped"] is None
    assert {
        key: result.decision for key, result in terminal.terminal_results.items()
    } == {"prior_h0": Decision.ACCEPT_H0, "winner": Decision.ACCEPT_H1}
    assert "skipped" not in terminal.terminal_results
    assert terminal.n_decided == 2
    assert terminal.n_total == 3
    assert run.n_observed == 2


def test_plain_core_import_does_not_import_pytest() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys\nimport montest\nassert 'pytest' not in sys.modules",
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
