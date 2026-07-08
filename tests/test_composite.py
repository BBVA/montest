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


def test_all_of_returns_none_for_child_results_after_that_child_decides() -> None:
    criterion = AllOf({"a": StopAfterN(2), "b": StopAfterN(4)})

    criterion.observe(object(), index=0)
    first_terminal = criterion.observe(object(), index=1)
    after_terminal = criterion.observe(object(), index=2)

    assert first_terminal.results["a"] is not None
    assert after_terminal.results["a"] is None
    assert isinstance(after_terminal.results["b"], ObservationResult)


def test_any_of_stops_when_first_child_accepts_h1() -> None:
    criterion = AnyOf({"a": StopAfterN(2), "b": StopAfterN(5)})

    first = criterion.observe(object(), index=0)
    terminal = criterion.observe(object(), index=1)

    assert first.decision is Decision.CONTINUE
    assert terminal.decision is Decision.ACCEPT_H1
    assert terminal.n_decided == terminal.n_total == 2
    assert terminal.results["a"] is not None
    assert terminal.results["a"].decision is Decision.ACCEPT_H1
    assert terminal.results["b"] is None


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
    assert results[-1].n_decided == results[-1].n_total == 2


def test_default_resolve_returns_inconclusive_when_no_child_accepts_h1() -> None:
    criterion = AllOf(
        {
            "a": StopAfterN(1, decision=Decision.INCONCLUSIVE),
            "b": StopAfterN(1, decision=Decision.ACCEPT_H0),
        }
    )

    result = criterion.observe(object(), index=0)

    assert result.decision is Decision.INCONCLUSIVE
    assert _child_decisions(result) == {
        "a": Decision.INCONCLUSIVE,
        "b": Decision.ACCEPT_H0,
    }


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
