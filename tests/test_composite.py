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

from collections.abc import Mapping

import pytest

from montest import AllOf, AnyOf, CompositeResult, Decision, ObservationResult, sprt
from tests.conftest import StopAfterN


def _child_decisions(
    result: CompositeResult[object],
) -> Mapping[str, Decision | None]:
    return {
        key: None if child is None else child.decision
        for key, child in result.results.items()
    }


def _terminal_child_decisions(
    result: CompositeResult[object],
) -> Mapping[str, Decision]:
    return {
        key: child.decision for key, child in result.terminal_results.items()
    }


def test_all_of_runs_until_longest_child_decides() -> None:
    criterion = AllOf({"a": StopAfterN(2), "b": StopAfterN(4)})

    results = [criterion.observe(object(), index=index) for index in range(4)]

    assert [result.index for result in results] == [0, 1, 2, 3]
    assert [result.n_decided for result in results] == [0, 1, 1, 2]
    assert [result.decision for result in results] == [
        Decision.CONTINUE,
        Decision.CONTINUE,
        Decision.CONTINUE,
        Decision.ACCEPT_H1,
    ]
    assert results[-1].n_total == 2
    assert [list(result.terminal_results) for result in results] == [
        [],
        ["a"],
        ["a"],
        ["a", "b"],
    ]
    assert all(
        result.n_decided == len(result.terminal_results) for result in results
    )


def test_all_of_returns_none_for_child_results_after_that_child_decides() -> None:
    criterion = AllOf({"a": StopAfterN(2), "b": StopAfterN(4)})

    criterion.observe(object(), index=0)
    first_terminal = criterion.observe(object(), index=1)
    after_terminal = criterion.observe(object(), index=2)

    assert first_terminal.results["a"] is not None
    assert after_terminal.results["a"] is None
    assert isinstance(after_terminal.results["b"], ObservationResult)
    assert first_terminal.terminal_results["a"] is first_terminal.results["a"]
    assert after_terminal.terminal_results["a"] is first_terminal.results["a"]
    assert after_terminal.n_decided == len(after_terminal.terminal_results) == 1


def test_any_of_stops_when_first_child_accepts_h1() -> None:
    criterion = AnyOf({"a": StopAfterN(2), "b": StopAfterN(5)})

    first = criterion.observe(object(), index=0)
    terminal = criterion.observe(object(), index=1)

    assert first.decision is Decision.CONTINUE
    assert terminal.decision is Decision.ACCEPT_H1
    assert terminal.n_decided == len(terminal.terminal_results) == 1
    assert terminal.results["a"] is not None
    assert terminal.results["a"].decision is Decision.ACCEPT_H1
    assert terminal.results["b"] is None
    assert terminal.n_total == 2
    assert terminal.terminal_results["a"] is terminal.results["a"]
    assert "b" not in terminal.terminal_results


def test_all_of_final_result_preserves_terminal_results_from_earlier_samples() -> None:
    criterion = AllOf({"a": StopAfterN(2), "b": StopAfterN(4)})

    results = [criterion.observe(object(), index=index) for index in range(4)]
    terminal = results[-1]

    assert terminal.decision is Decision.ACCEPT_H1
    assert terminal.results["a"] is None
    assert terminal.results["b"] is terminal.terminal_results["b"]
    assert terminal.terminal_results["a"] is results[1].results["a"]
    assert terminal.terminal_results["a"].index == 1
    assert terminal.terminal_results["a"].decision is Decision.ACCEPT_H1
    assert terminal.terminal_results["b"].index == 3
    assert (
        terminal.n_decided
        == len(terminal.terminal_results)
        == terminal.n_total
        == 2
    )


def test_any_of_early_accept_h1_preserves_prior_terminal_evidence_only() -> None:
    criterion = AnyOf(
        {
            "prior_h0": StopAfterN(1, decision=Decision.ACCEPT_H0),
            "winner": StopAfterN(2, decision=Decision.ACCEPT_H1),
            "skipped": StopAfterN(5, decision=Decision.ACCEPT_H0),
        }
    )

    first = criterion.observe(object(), index=0)
    terminal = criterion.observe(object(), index=1)

    assert first.decision is Decision.CONTINUE
    assert _terminal_child_decisions(first) == {"prior_h0": Decision.ACCEPT_H0}
    assert terminal.decision is Decision.ACCEPT_H1
    assert terminal.results["prior_h0"] is None
    assert terminal.results["winner"] is terminal.terminal_results["winner"]
    assert terminal.results["skipped"] is None
    assert _terminal_child_decisions(terminal) == {
        "prior_h0": Decision.ACCEPT_H0,
        "winner": Decision.ACCEPT_H1,
    }
    assert "skipped" not in terminal.terminal_results
    assert terminal.n_decided == len(terminal.terminal_results) == 2
    assert terminal.n_decided < terminal.n_total == 3


def test_any_of_waits_for_all_children_when_no_child_accepts_h1() -> None:
    criterion = AnyOf(
        {
            "a": StopAfterN(2, decision=Decision.ACCEPT_H0),
            "b": StopAfterN(4, decision=Decision.ACCEPT_H0),
        }
    )

    results = [criterion.observe(object(), index=index) for index in range(4)]

    assert [result.decision for result in results] == [
        Decision.CONTINUE,
        Decision.CONTINUE,
        Decision.CONTINUE,
        Decision.ACCEPT_H0,
    ]
    assert results[2].results["a"] is None
    assert results[-1].n_decided == len(results[-1].terminal_results) == 2
    assert results[-1].n_total == 2


def test_all_of_resolves_accept_h0_over_inconclusive() -> None:
    criterion = AllOf(
        {
            "a": StopAfterN(1, decision=Decision.INCONCLUSIVE),
            "b": StopAfterN(1, decision=Decision.ACCEPT_H0),
        }
    )

    result = criterion.observe(object(), index=0)

    assert result.decision is Decision.ACCEPT_H0
    assert _child_decisions(result) == {
        "a": Decision.INCONCLUSIVE,
        "b": Decision.ACCEPT_H0,
    }


def test_all_of_resolves_inconclusive_when_no_child_accepts_h0() -> None:
    criterion = AllOf(
        {
            "a": StopAfterN(1, decision=Decision.ACCEPT_H1),
            "b": StopAfterN(1, decision=Decision.INCONCLUSIVE),
        }
    )

    result = criterion.observe(object(), index=0)

    assert result.decision is Decision.INCONCLUSIVE
    assert _child_decisions(result) == {
        "a": Decision.ACCEPT_H1,
        "b": Decision.INCONCLUSIVE,
    }


def test_all_of_resolves_accept_h1_when_all_children_accept_h1() -> None:
    criterion = AllOf(
        {
            "a": StopAfterN(1, decision=Decision.ACCEPT_H1),
            "b": StopAfterN(1, decision=Decision.ACCEPT_H1),
        }
    )

    result = criterion.observe(object(), index=0)

    assert result.decision is Decision.ACCEPT_H1
    assert _child_decisions(result) == {
        "a": Decision.ACCEPT_H1,
        "b": Decision.ACCEPT_H1,
    }


def test_any_of_resolves_inconclusive_after_all_children_terminal() -> None:
    criterion = AnyOf(
        {
            "a": StopAfterN(1, decision=Decision.ACCEPT_H0),
            "b": StopAfterN(3, decision=Decision.INCONCLUSIVE),
            "c": StopAfterN(2, decision=Decision.ACCEPT_H0),
        }
    )

    results = [criterion.observe(object(), index=index) for index in range(3)]

    assert [result.decision for result in results] == [
        Decision.CONTINUE,
        Decision.CONTINUE,
        Decision.INCONCLUSIVE,
    ]
    assert results[-1].n_decided == len(results[-1].terminal_results) == 3
    assert results[-1].n_total == 3
    assert _child_decisions(results[-1]) == {
        "a": None,
        "b": Decision.INCONCLUSIVE,
        "c": None,
    }
    assert _terminal_child_decisions(results[-1]) == {
        "a": Decision.ACCEPT_H0,
        "b": Decision.INCONCLUSIVE,
        "c": Decision.ACCEPT_H0,
    }


def test_nested_composite_terminal_result_preserves_direct_parent_key() -> None:
    nested = AllOf(
        {
            "inner_a": StopAfterN(1, decision=Decision.ACCEPT_H0),
            "inner_b": StopAfterN(2, decision=Decision.ACCEPT_H0),
        }
    )
    parent = AllOf({"nested": nested, "outer": StopAfterN(3)})

    parent.observe(object(), index=0)
    nested_terminal_step = parent.observe(object(), index=1)
    parent_terminal = parent.observe(object(), index=2)

    assert nested_terminal_step.results["nested"] is not None
    assert isinstance(nested_terminal_step.results["nested"], CompositeResult)
    assert nested_terminal_step.terminal_results["nested"] is (
        nested_terminal_step.results["nested"]
    )
    assert parent_terminal.results["nested"] is None
    nested_terminal = parent_terminal.terminal_results["nested"]
    assert isinstance(nested_terminal, CompositeResult)
    assert nested_terminal is nested_terminal_step.results["nested"]
    assert list(parent_terminal.terminal_results) == ["nested", "outer"]
    assert "inner_a" not in parent_terminal.terminal_results
    assert "inner_b" not in parent_terminal.terminal_results
    assert list(nested_terminal.terminal_results) == ["inner_a", "inner_b"]
    assert parent_terminal.n_decided == len(parent_terminal.terminal_results) == 2


def test_composite_rejects_empty_criteria_mapping() -> None:
    with pytest.raises(ValueError, match="^criteria must not be empty$"):
        AllOf({})


def test_composite_rejects_empty_string_key() -> None:
    with pytest.raises(ValueError, match="^criterion keys must be non-empty strings$"):
        AnyOf({"": StopAfterN(1)})


def test_composite_observe_after_terminal_decision_raises_runtime_error() -> None:
    criterion = AnyOf({"a": StopAfterN(1)})
    criterion.observe(object(), index=0)

    with pytest.raises(RuntimeError, match="Criterion already reached a decision"):
        criterion.observe(object(), index=1)


def test_composite_reset_reproduces_same_decision_sequence() -> None:
    criterion = AllOf(
        {
            "a": StopAfterN(1, decision=Decision.ACCEPT_H0),
            "b": StopAfterN(3, decision=Decision.INCONCLUSIVE),
        }
    )

    first_sequence = []
    for index in range(3):
        result = criterion.observe(object(), index=index)
        first_sequence.append(
            (result.decision, result.n_decided, _child_decisions(result))
        )

    criterion.reset()

    second_sequence = []
    for index in range(3):
        result = criterion.observe(object(), index=index)
        second_sequence.append(
            (result.decision, result.n_decided, _child_decisions(result))
        )

    assert second_sequence == first_sequence


def test_sprt_does_not_expose_operator_composition_api() -> None:
    with pytest.raises(TypeError):
        sprt(llr=lambda _: 0.0) & sprt(llr=lambda _: 0.0)
