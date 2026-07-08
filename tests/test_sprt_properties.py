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
import math

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from montest import Decision, SPRTResult, sprt

FINITE_LLR = st.floats(
    min_value=-5.0,
    max_value=5.0,
    allow_nan=False,
    allow_infinity=False,
    width=64,
)
ERROR_RATE = st.floats(
    min_value=0.01,
    max_value=0.40,
    allow_nan=False,
    allow_infinity=False,
    width=64,
)


@dataclasses.dataclass(frozen=True, slots=True)
class SPRTCase:
    increments: tuple[float, ...]
    alpha: float
    beta: float
    max_samples: int | None


@dataclasses.dataclass(frozen=True, slots=True)
class ExpectedSPRTResult:
    value: float
    index: int
    decision: Decision
    cumulative_llr: float
    lower_bound: float
    upper_bound: float
    n_observed: int


@st.composite
def terminal_sprt_cases(draw: st.DrawFn) -> SPRTCase:
    alpha = draw(ERROR_RATE)
    beta = draw(ERROR_RATE)
    increments = list(draw(st.lists(FINITE_LLR, min_size=1, max_size=30)))
    use_max_samples = draw(st.booleans())

    if use_max_samples:
        max_samples = draw(st.integers(min_value=1, max_value=len(increments)))
    else:
        max_samples = None
        lower_bound = math.log(beta / (1.0 - alpha))
        upper_bound = math.log((1.0 - beta) / alpha)
        if not _trace_crosses_boundary(increments, lower_bound, upper_bound):
            cumulative_llr = sum(increments)
            increments.append(upper_bound - cumulative_llr + 0.5)

    return SPRTCase(
        increments=tuple(increments),
        alpha=alpha,
        beta=beta,
        max_samples=max_samples,
    )


def _trace_crosses_boundary(
    increments: list[float], lower_bound: float, upper_bound: float
) -> bool:
    cumulative_llr = 0.0
    for increment in increments:
        cumulative_llr += increment
        if cumulative_llr >= upper_bound or cumulative_llr <= lower_bound:
            return True
    return False


def _sprt_oracle(case: SPRTCase) -> list[ExpectedSPRTResult]:
    lower_bound = math.log(case.beta / (1.0 - case.alpha))
    upper_bound = math.log((1.0 - case.beta) / case.alpha)
    cumulative_llr = 0.0
    results: list[ExpectedSPRTResult] = []

    for index, increment in enumerate(case.increments):
        cumulative_llr += increment
        n_observed = index + 1
        decision = Decision.CONTINUE
        if cumulative_llr >= upper_bound:
            decision = Decision.ACCEPT_H1
        elif cumulative_llr <= lower_bound:
            decision = Decision.ACCEPT_H0
        elif case.max_samples is not None and n_observed >= case.max_samples:
            decision = Decision.INCONCLUSIVE

        results.append(
            ExpectedSPRTResult(
                value=increment,
                index=index,
                decision=decision,
                cumulative_llr=cumulative_llr,
                lower_bound=lower_bound,
                upper_bound=upper_bound,
                n_observed=n_observed,
            )
        )
        if decision is not Decision.CONTINUE:
            break

    return results


def _observe_case(case: SPRTCase) -> list[SPRTResult[float]]:
    criterion = sprt(
        llr=lambda sample: sample,
        alpha=case.alpha,
        beta=case.beta,
        max_samples=case.max_samples,
    )
    results: list[SPRTResult[float]] = []
    for index, increment in enumerate(case.increments):
        result = criterion.observe(increment, index=index)
        results.append(result)
        if result.decision is not Decision.CONTINUE:
            break
    return results


def _assert_result_matches_oracle(
    result: SPRTResult[float], expected: ExpectedSPRTResult
) -> None:
    assert result.value == expected.value
    assert result.index == expected.index
    assert result.decision is expected.decision
    assert result.n_observed == expected.n_observed
    assert math.isclose(result.cumulative_llr, expected.cumulative_llr)
    assert math.isclose(result.lower_bound, expected.lower_bound)
    assert math.isclose(result.upper_bound, expected.upper_bound)


def _assert_trace_matches_oracle(case: SPRTCase) -> None:
    criterion = sprt(
        llr=lambda sample: sample,
        alpha=case.alpha,
        beta=case.beta,
        max_samples=case.max_samples,
    )
    expected_results = _sprt_oracle(case)

    for expected in expected_results:
        result = criterion.observe(expected.value, index=expected.index)
        _assert_result_matches_oracle(result, expected)

    assert expected_results[-1].decision is not Decision.CONTINUE
    with pytest.raises(RuntimeError, match="Criterion already reached a decision"):
        criterion.observe(0.0, index=len(expected_results))


def _dual(decision: Decision) -> Decision:
    if decision is Decision.ACCEPT_H1:
        return Decision.ACCEPT_H0
    if decision is Decision.ACCEPT_H0:
        return Decision.ACCEPT_H1
    return decision


def _is_far_from_boundaries(case: SPRTCase) -> bool:
    lower_bound = math.log(case.beta / (1.0 - case.alpha))
    upper_bound = math.log((1.0 - case.beta) / case.alpha)
    dual_lower_bound = math.log(case.alpha / (1.0 - case.beta))
    dual_upper_bound = math.log((1.0 - case.alpha) / case.beta)
    cumulative_llr = 0.0
    for increment in case.increments:
        cumulative_llr += increment
        if (
            math.isclose(cumulative_llr, lower_bound, abs_tol=1e-10)
            or math.isclose(cumulative_llr, upper_bound, abs_tol=1e-10)
            or math.isclose(-cumulative_llr, dual_lower_bound, abs_tol=1e-10)
            or math.isclose(-cumulative_llr, dual_upper_bound, abs_tol=1e-10)
        ):
            return False
    return True


@settings(max_examples=100, deadline=None, derandomize=True)
@given(case=terminal_sprt_cases())
def test_sprt_matches_oracle_for_finite_llr_traces(case: SPRTCase) -> None:
    _assert_trace_matches_oracle(case)


@settings(max_examples=100, deadline=None, derandomize=True)
@given(case=terminal_sprt_cases())
def test_sprt_reset_replays_oracle_trace(case: SPRTCase) -> None:
    criterion = sprt(
        llr=lambda sample: sample,
        alpha=case.alpha,
        beta=case.beta,
        max_samples=case.max_samples,
    )
    expected_results = _sprt_oracle(case)

    first_trace = [
        criterion.observe(expected.value, index=expected.index)
        for expected in expected_results
    ]
    for actual, expected in zip(first_trace, expected_results, strict=True):
        _assert_result_matches_oracle(actual, expected)

    criterion.reset()
    assert criterion.cumulative_llr == 0.0
    assert criterion.n_observed == 0

    second_trace = [
        criterion.observe(expected.value, index=expected.index)
        for expected in expected_results
    ]
    assert second_trace == first_trace
    with pytest.raises(RuntimeError, match="Criterion already reached a decision"):
        criterion.observe(0.0, index=len(expected_results))


@settings(max_examples=75, deadline=None, derandomize=True)
@given(alpha=ERROR_RATE, beta=ERROR_RATE)
def test_sprt_boundary_equality_is_terminal(alpha: float, beta: float) -> None:
    lower_bound = math.log(beta / (1.0 - alpha))
    upper_bound = math.log((1.0 - beta) / alpha)

    upper_result = sprt(llr=lambda sample: sample, alpha=alpha, beta=beta).observe(
        upper_bound, index=0
    )
    assert upper_result.decision is Decision.ACCEPT_H1
    assert math.isclose(upper_result.cumulative_llr, upper_bound)

    lower_result = sprt(llr=lambda sample: sample, alpha=alpha, beta=beta).observe(
        lower_bound, index=0
    )
    assert lower_result.decision is Decision.ACCEPT_H0
    assert math.isclose(lower_result.cumulative_llr, lower_bound)


@settings(max_examples=100, deadline=None, derandomize=True)
@given(case=terminal_sprt_cases())
def test_sprt_dual_sign_trace_swaps_h0_h1(case: SPRTCase) -> None:
    assume(_is_far_from_boundaries(case))
    dual_case = SPRTCase(
        increments=tuple(-increment for increment in case.increments),
        alpha=case.beta,
        beta=case.alpha,
        max_samples=case.max_samples,
    )

    original_results = _observe_case(case)
    dual_results = _observe_case(dual_case)

    assert len(dual_results) == len(original_results)
    for original, dual in zip(original_results, dual_results, strict=True):
        assert dual.index == original.index
        assert dual.value == -original.value
        assert math.isclose(dual.cumulative_llr, -original.cumulative_llr)
        assert math.isclose(dual.lower_bound, -original.upper_bound)
        assert math.isclose(dual.upper_bound, -original.lower_bound)
        assert dual.n_observed == original.n_observed
        assert dual.decision is _dual(original.decision)
