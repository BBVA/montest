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

import dataclasses
from collections.abc import Callable, Mapping

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from montest import (
    ALL_OF_DECISION_MONOID,
    ANY_OF_DECISION_MONOID,
    AllOf,
    AnyOf,
    CompositeResult,
    Decision,
    ObservationResult,
)

TERMINAL_DECISIONS = st.sampled_from(
    [Decision.ACCEPT_H1, Decision.ACCEPT_H0, Decision.INCONCLUSIVE]
)
CompositeFactory = Callable[[Mapping[str, object]], AllOf[object] | AnyOf[object]]


@dataclasses.dataclass(frozen=True, slots=True)
class ChildScript:
    name: str
    terminal_after: int
    terminal_decision: Decision


@dataclasses.dataclass(frozen=True, slots=True)
class ExpectedChildResult:
    value: int
    index: int
    decision: Decision


@dataclasses.dataclass(frozen=True, slots=True)
class ExpectedCompositeResult:
    value: int
    index: int
    decision: Decision
    results: Mapping[str, ExpectedChildResult | None]
    n_decided: int
    n_total: int


class ScriptedCriterion:
    def __init__(self, terminal_after: int, terminal_decision: Decision) -> None:
        self._terminal_after = terminal_after
        self._terminal_decision = terminal_decision
        self._observed_count = 0
        self._terminal = False
        self._observed_indices: list[int] = []

    @property
    def observed_indices(self) -> tuple[int, ...]:
        return tuple(self._observed_indices)

    def observe(self, sample: object, *, index: int) -> ObservationResult[object]:
        if self._terminal:
            raise AssertionError("terminal scripted criterion was observed again")

        self._observed_count += 1
        self._observed_indices.append(index)
        decision = Decision.CONTINUE
        if self._observed_count >= self._terminal_after:
            decision = self._terminal_decision
            self._terminal = True

        return ObservationResult(value=sample, index=index, decision=decision)

    def reset(self) -> None:
        self._observed_count = 0
        self._terminal = False
        self._observed_indices.clear()


@st.composite
def child_scripts(draw: st.DrawFn) -> tuple[ChildScript, ...]:
    size = draw(st.integers(min_value=1, max_value=6))
    terminal_after_values = draw(
        st.lists(st.integers(min_value=1, max_value=20), min_size=size, max_size=size)
    )
    terminal_decisions = draw(
        st.lists(TERMINAL_DECISIONS, min_size=size, max_size=size)
    )
    return tuple(
        ChildScript(
            name=f"child_{index}",
            terminal_after=terminal_after_values[index],
            terminal_decision=terminal_decisions[index],
        )
        for index in range(size)
    )


def _criteria_from_scripts(
    scripts: tuple[ChildScript, ...],
) -> dict[str, ScriptedCriterion]:
    return {
        script.name: ScriptedCriterion(
            script.terminal_after, script.terminal_decision
        )
        for script in scripts
    }


def _all_of_resolve(decisions: list[Decision]) -> Decision:
    return ALL_OF_DECISION_MONOID.resolve(decisions)


def _any_of_resolve(decisions: list[Decision]) -> Decision:
    return ANY_OF_DECISION_MONOID.resolve(decisions)


def _terminal_sequence(
    scripts: tuple[ChildScript, ...], terminal_decisions: Mapping[str, Decision]
) -> list[Decision]:
    return [
        terminal_decisions[script.name]
        for script in scripts
        if script.name in terminal_decisions
    ]


def _all_of_oracle(
    scripts: tuple[ChildScript, ...],
) -> tuple[list[ExpectedCompositeResult], dict[str, tuple[int, ...]]]:
    observed_counts = {script.name: 0 for script in scripts}
    observed_indices: dict[str, list[int]] = {script.name: [] for script in scripts}
    terminal_decisions: dict[str, Decision] = {}
    results: list[ExpectedCompositeResult] = []

    for index in range(max(script.terminal_after for script in scripts)):
        child_results: dict[str, ExpectedChildResult | None] = {}
        for script in scripts:
            if script.name in terminal_decisions:
                child_results[script.name] = None
                continue

            observed_counts[script.name] += 1
            observed_indices[script.name].append(index)
            decision = Decision.CONTINUE
            if observed_counts[script.name] >= script.terminal_after:
                decision = script.terminal_decision
                terminal_decisions[script.name] = decision
            child_results[script.name] = ExpectedChildResult(
                value=index, index=index, decision=decision
            )

        n_decided = len(terminal_decisions)
        decision = Decision.CONTINUE
        if n_decided == len(scripts):
            decision = _all_of_resolve(_terminal_sequence(scripts, terminal_decisions))

        results.append(
            ExpectedCompositeResult(
                value=index,
                index=index,
                decision=decision,
                results=child_results,
                n_decided=n_decided,
                n_total=len(scripts),
            )
        )
        if decision is not Decision.CONTINUE:
            return results, {
                name: tuple(indices) for name, indices in observed_indices.items()
            }

    raise AssertionError("AllOf oracle did not terminate")


def _any_of_oracle(
    scripts: tuple[ChildScript, ...],
) -> tuple[list[ExpectedCompositeResult], dict[str, tuple[int, ...]]]:
    observed_counts = {script.name: 0 for script in scripts}
    observed_indices: dict[str, list[int]] = {script.name: [] for script in scripts}
    terminal_decisions: dict[str, Decision] = {}
    results: list[ExpectedCompositeResult] = []

    for index in range(max(script.terminal_after for script in scripts)):
        child_results: dict[str, ExpectedChildResult | None] = {}
        stopped_early = False
        for script in scripts:
            if script.name in terminal_decisions or stopped_early:
                child_results[script.name] = None
                continue

            observed_counts[script.name] += 1
            observed_indices[script.name].append(index)
            decision = Decision.CONTINUE
            if observed_counts[script.name] >= script.terminal_after:
                decision = script.terminal_decision
                terminal_decisions[script.name] = decision
                if decision is Decision.ACCEPT_H1:
                    stopped_early = True
            child_results[script.name] = ExpectedChildResult(
                value=index, index=index, decision=decision
            )

        n_decided = len(terminal_decisions)
        decision = Decision.CONTINUE
        if stopped_early:
            decision = _any_of_resolve(_terminal_sequence(scripts, terminal_decisions))
            n_decided = len(scripts)
        elif n_decided == len(scripts):
            decision = _any_of_resolve(_terminal_sequence(scripts, terminal_decisions))

        results.append(
            ExpectedCompositeResult(
                value=index,
                index=index,
                decision=decision,
                results=child_results,
                n_decided=n_decided,
                n_total=len(scripts),
            )
        )
        if decision is not Decision.CONTINUE:
            return results, {
                name: tuple(indices) for name, indices in observed_indices.items()
            }

    raise AssertionError("AnyOf oracle did not terminate")


def _assert_composite_result_matches(
    actual: CompositeResult[object], expected: ExpectedCompositeResult
) -> None:
    assert actual.value == expected.value
    assert actual.index == expected.index
    assert actual.decision is expected.decision
    assert actual.n_decided == expected.n_decided
    assert actual.n_total == expected.n_total
    assert list(actual.results) == list(expected.results)

    for key, expected_child in expected.results.items():
        actual_child = actual.results[key]
        if expected_child is None:
            assert actual_child is None
            continue

        assert isinstance(actual_child, ObservationResult)
        assert actual_child.value == expected_child.value
        assert actual_child.index == expected_child.index
        assert actual_child.decision is expected_child.decision


def _run_until_terminal(
    criterion: AllOf[object] | AnyOf[object], *, max_steps: int = 25
) -> list[CompositeResult[object]]:
    results: list[CompositeResult[object]] = []
    for index in range(max_steps):
        result = criterion.observe(index, index=index)
        results.append(result)
        if result.decision is not Decision.CONTINUE:
            return results
    raise AssertionError("composite did not terminate")


def _direct_signature(
    result: CompositeResult[object],
) -> tuple[object, ...]:
    return (
        result.value,
        result.index,
        result.decision,
        result.n_decided,
        result.n_total,
        tuple(
            (
                key,
                None
                if child is None
                else (child.value, child.index, child.decision),
            )
            for key, child in result.results.items()
        ),
    )


def _nested_signature(result: ObservationResult[object] | None) -> object:
    if result is None:
        return None
    if isinstance(result, CompositeResult):
        return (
            result.value,
            result.index,
            result.decision,
            result.n_decided,
            result.n_total,
            tuple(
                (key, _nested_signature(child))
                for key, child in result.results.items()
            ),
        )
    return result.value, result.index, result.decision


@settings(max_examples=75, deadline=None, derandomize=True)
@given(scripts=child_scripts())
def test_all_of_matches_direct_composite_oracle(
    scripts: tuple[ChildScript, ...]
) -> None:
    criteria = _criteria_from_scripts(scripts)
    criterion = AllOf(criteria)
    expected_results, expected_indices = _all_of_oracle(scripts)

    for expected in expected_results:
        actual = criterion.observe(expected.value, index=expected.index)
        _assert_composite_result_matches(actual, expected)

    assert expected_results[-1].decision is _all_of_resolve(
        [script.terminal_decision for script in scripts]
    )
    assert {
        name: criterion.observed_indices for name, criterion in criteria.items()
    } == expected_indices
    with pytest.raises(RuntimeError, match="Criterion already reached a decision"):
        criterion.observe(0, index=len(expected_results))


@settings(max_examples=75, deadline=None, derandomize=True)
@given(scripts=child_scripts())
def test_any_of_matches_direct_composite_oracle(
    scripts: tuple[ChildScript, ...]
) -> None:
    criteria = _criteria_from_scripts(scripts)
    criterion = AnyOf(criteria)
    expected_results, expected_indices = _any_of_oracle(scripts)

    for expected in expected_results:
        actual = criterion.observe(expected.value, index=expected.index)
        _assert_composite_result_matches(actual, expected)

    if all(script.terminal_decision is not Decision.ACCEPT_H1 for script in scripts):
        assert len(expected_results) == max(script.terminal_after for script in scripts)
    assert {
        name: criterion.observed_indices for name, criterion in criteria.items()
    } == expected_indices
    with pytest.raises(RuntimeError, match="Criterion already reached a decision"):
        criterion.observe(0, index=len(expected_results))


@pytest.mark.parametrize("composite_factory", [AllOf, AnyOf])
@settings(max_examples=75, deadline=None, derandomize=True)
@given(scripts=child_scripts())
def test_composite_reset_replays_trace(
    composite_factory: CompositeFactory, scripts: tuple[ChildScript, ...]
) -> None:
    criteria = _criteria_from_scripts(scripts)
    criterion = composite_factory(criteria)

    first_trace = [
        _direct_signature(result) for result in _run_until_terminal(criterion)
    ]
    criterion.reset()
    assert all(not child.observed_indices for child in criteria.values())
    second_trace = [
        _direct_signature(result) for result in _run_until_terminal(criterion)
    ]

    assert second_trace == first_trace


@pytest.mark.parametrize(
    ("parent_factory", "nested_factory"),
    [(AllOf, AllOf), (AllOf, AnyOf), (AnyOf, AllOf), (AnyOf, AnyOf)],
)
@settings(max_examples=25, deadline=None, derandomize=True)
@given(
    inner_left_after=st.integers(min_value=1, max_value=4),
    inner_left_decision=TERMINAL_DECISIONS,
    inner_right_after=st.integers(min_value=1, max_value=4),
    inner_right_decision=TERMINAL_DECISIONS,
    outer_after=st.integers(min_value=1, max_value=4),
    outer_decision=TERMINAL_DECISIONS,
)
def test_nested_composite_results_are_preserved_under_direct_keys(
    parent_factory: CompositeFactory,
    nested_factory: CompositeFactory,
    inner_left_after: int,
    inner_left_decision: Decision,
    inner_right_after: int,
    inner_right_decision: Decision,
    outer_after: int,
    outer_decision: Decision,
) -> None:
    inner_left = ScriptedCriterion(inner_left_after, inner_left_decision)
    inner_right = ScriptedCriterion(inner_right_after, inner_right_decision)
    nested = nested_factory({"inner_a": inner_left, "inner_b": inner_right})
    outer = ScriptedCriterion(outer_after, outer_decision)
    parent = parent_factory({"nested": nested, "outer": outer})

    first_trace = _run_until_terminal(parent, max_steps=8)
    seen_nested_result = False
    for result in first_trace:
        assert list(result.results) == ["nested", "outer"]
        assert "inner_a" not in result.results
        assert "inner_b" not in result.results
        assert result.n_total == 2
        assert result.n_decided <= 2

        nested_result = result.results["nested"]
        if nested_result is None:
            continue
        assert isinstance(nested_result, CompositeResult)
        assert list(nested_result.results) == ["inner_a", "inner_b"]
        assert nested_result.n_total == 2
        seen_nested_result = True

    assert seen_nested_result
    assert first_trace[-1].n_decided == 2

    parent.reset()
    second_trace = _run_until_terminal(parent, max_steps=8)
    assert [_nested_signature(result) for result in second_trace] == [
        _nested_signature(result) for result in first_trace
    ]
