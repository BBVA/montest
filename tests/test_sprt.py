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

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from montest import Decision, SPRTResult, sprt


def test_sprt_computes_wald_bounds() -> None:
    criterion = sprt(llr=lambda _: 0.0, alpha=0.05, beta=0.10)

    assert math.isclose(criterion.lower_bound, math.log(0.10 / (1.0 - 0.05)))
    assert math.isclose(criterion.upper_bound, math.log((1.0 - 0.10) / 0.05))


def test_sprt_accepts_h1_when_positive_llr_crosses_upper_bound() -> None:
    result = sprt(llr=lambda _: 10.0).observe("sample", index=7)

    assert result.value == "sample"
    assert result.index == 7
    assert result.decision is Decision.ACCEPT_H1


def test_sprt_accepts_h0_when_negative_llr_crosses_lower_bound() -> None:
    result = sprt(llr=lambda _: -10.0).observe("sample", index=3)

    assert result.decision is Decision.ACCEPT_H0


def test_sprt_continues_while_cumulative_llr_stays_inside_bounds() -> None:
    result = sprt(llr=lambda _: 0.0).observe("sample", index=0)

    assert result.decision is Decision.CONTINUE
    assert result.cumulative_llr == 0.0
    assert result.n_observed == 1


def test_sprt_accumulates_llr_until_repeated_observations_cross_upper_bound() -> None:
    criterion = sprt(llr=lambda _: 1.0, alpha=0.05, beta=0.10)

    decisions = [
        criterion.observe("sample", index=index).decision for index in range(3)
    ]

    assert decisions == [Decision.CONTINUE, Decision.CONTINUE, Decision.ACCEPT_H1]
    assert criterion.cumulative_llr == 3.0
    assert criterion.n_observed == 3


def test_sprt_result_includes_observation_bounds_and_accumulated_state() -> None:
    criterion = sprt(llr=lambda sample: float(sample), alpha=0.05, beta=0.10)

    result = criterion.observe(1.25, index=42)

    assert isinstance(result, SPRTResult)
    assert result.value == 1.25
    assert result.index == 42
    assert result.decision is Decision.CONTINUE
    assert result.cumulative_llr == 1.25
    assert result.lower_bound == criterion.lower_bound
    assert result.upper_bound == criterion.upper_bound
    assert result.n_observed == 1


def test_sprt_returns_inconclusive_when_max_samples_reached_inside_bounds() -> None:
    criterion = sprt(llr=lambda _: 0.0, max_samples=2)

    first = criterion.observe("first", index=0)
    second = criterion.observe("second", index=1)

    assert first.decision is Decision.CONTINUE
    assert second.decision is Decision.INCONCLUSIVE
    assert second.n_observed == 2


def test_sprt_reset_clears_state_and_allows_reuse_after_terminal_decision() -> None:
    criterion = sprt(llr=lambda _: 10.0)

    terminal = criterion.observe("first", index=0)
    criterion.reset()

    assert terminal.decision is Decision.ACCEPT_H1
    assert criterion.cumulative_llr == 0.0
    assert criterion.n_observed == 0

    reused = criterion.observe("second", index=0)

    assert criterion.cumulative_llr == 10.0
    assert criterion.n_observed == 1
    assert reused.value == "second"
    assert reused.decision is Decision.ACCEPT_H1


def test_sprt_observe_after_terminal_decision_raises_runtime_error() -> None:
    criterion = sprt(llr=lambda _: 10.0)
    criterion.observe("sample", index=0)

    with pytest.raises(RuntimeError, match="Criterion already reached a decision"):
        criterion.observe("sample", index=1)


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"alpha": 0.0}, "alpha"),
        ({"alpha": 1.0}, "alpha"),
        ({"beta": 0.0}, "beta"),
        ({"beta": 1.0}, "beta"),
        ({"max_samples": 0}, "max_samples"),
    ],
)
def test_sprt_rejects_invalid_error_rates_and_sample_limits(
    kwargs: dict[str, float | int],
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        sprt(llr=lambda _: 0.0, **kwargs)


@given(
    st.lists(
        st.floats(
            min_value=-2.0,
            max_value=2.0,
            allow_nan=False,
            allow_infinity=False,
            width=32,
        ),
        min_size=1,
        max_size=30,
    )
)
def test_sprt_reset_replays_same_decision_trace(increments: list[float]) -> None:
    criterion = sprt(llr=lambda sample: sample, max_samples=len(increments))

    first_trace = []
    for index, increment in enumerate(increments):
        result = criterion.observe(increment, index=index)
        first_trace.append((result.decision, result.cumulative_llr, result.n_observed))
        if result.decision is not Decision.CONTINUE:
            break

    criterion.reset()

    second_trace = []
    for index, increment in enumerate(increments):
        result = criterion.observe(increment, index=index)
        second_trace.append((result.decision, result.cumulative_llr, result.n_observed))
        if result.decision is not Decision.CONTINUE:
            break

    assert second_trace == first_trace
