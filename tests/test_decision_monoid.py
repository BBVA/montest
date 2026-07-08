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

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from montest import (
    ALL_OF_DECISION_MONOID,
    ANY_OF_DECISION_MONOID,
    Decision,
    DecisionMonoid,
)

TERMINAL_DECISIONS = st.sampled_from(
    [Decision.ACCEPT_H1, Decision.ACCEPT_H0, Decision.INCONCLUSIVE]
)
DECISION_MONOIDS = [
    pytest.param(ANY_OF_DECISION_MONOID, id="any_of"),
    pytest.param(ALL_OF_DECISION_MONOID, id="all_of"),
]


def _fold(monoid: DecisionMonoid, decisions: list[Decision]) -> Decision:
    result = monoid.identity
    for decision in decisions:
        result = monoid.combine(result, decision)
    return result


@pytest.mark.parametrize("monoid", DECISION_MONOIDS)
@settings(max_examples=75, deadline=None, derandomize=True)
@given(a=TERMINAL_DECISIONS, b=TERMINAL_DECISIONS, c=TERMINAL_DECISIONS)
def test_decision_monoid_combine_is_associative(
    monoid: DecisionMonoid, a: Decision, b: Decision, c: Decision
) -> None:
    assert monoid.combine(a, monoid.combine(b, c)) is monoid.combine(
        monoid.combine(a, b), c
    )


@pytest.mark.parametrize("monoid", DECISION_MONOIDS)
@settings(max_examples=75, deadline=None, derandomize=True)
@given(decision=TERMINAL_DECISIONS)
def test_decision_monoid_identity_is_neutral(
    monoid: DecisionMonoid, decision: Decision
) -> None:
    assert monoid.combine(monoid.identity, decision) is decision
    assert monoid.combine(decision, monoid.identity) is decision


@pytest.mark.parametrize("monoid", DECISION_MONOIDS)
@settings(max_examples=75, deadline=None, derandomize=True)
@given(decisions=st.lists(TERMINAL_DECISIONS, max_size=25))
def test_decision_monoid_resolve_is_left_fold_from_identity(
    monoid: DecisionMonoid, decisions: list[Decision]
) -> None:
    assert monoid.resolve(decisions) is _fold(monoid, decisions)


@settings(max_examples=75, deadline=None, derandomize=True)
@given(other=TERMINAL_DECISIONS)
def test_any_of_accept_h1_is_absorbing_for_combine(other: Decision) -> None:
    assert (
        ANY_OF_DECISION_MONOID.combine(Decision.ACCEPT_H1, other)
        is Decision.ACCEPT_H1
    )
    assert (
        ANY_OF_DECISION_MONOID.combine(other, Decision.ACCEPT_H1)
        is Decision.ACCEPT_H1
    )


@settings(max_examples=75, deadline=None, derandomize=True)
@given(
    prefix=st.lists(TERMINAL_DECISIONS, max_size=10),
    suffix=st.lists(TERMINAL_DECISIONS, max_size=10),
)
def test_any_of_accept_h1_dominates_resolution(
    prefix: list[Decision], suffix: list[Decision]
) -> None:
    assert (
        ANY_OF_DECISION_MONOID.resolve(prefix + [Decision.ACCEPT_H1] + suffix)
        is Decision.ACCEPT_H1
    )


@settings(max_examples=75, deadline=None, derandomize=True)
@given(other=TERMINAL_DECISIONS)
def test_all_of_accept_h0_is_absorbing_for_combine(other: Decision) -> None:
    assert (
        ALL_OF_DECISION_MONOID.combine(Decision.ACCEPT_H0, other)
        is Decision.ACCEPT_H0
    )
    assert (
        ALL_OF_DECISION_MONOID.combine(other, Decision.ACCEPT_H0)
        is Decision.ACCEPT_H0
    )


@settings(max_examples=75, deadline=None, derandomize=True)
@given(
    prefix=st.lists(TERMINAL_DECISIONS, max_size=10),
    suffix=st.lists(TERMINAL_DECISIONS, max_size=10),
)
def test_all_of_accept_h0_dominates_resolution(
    prefix: list[Decision], suffix: list[Decision]
) -> None:
    assert (
        ALL_OF_DECISION_MONOID.resolve(prefix + [Decision.ACCEPT_H0] + suffix)
        is Decision.ACCEPT_H0
    )
