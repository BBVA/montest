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
# ruff: noqa: E501

"""Copyable tests for detecting a meaningful coin bias.

Question: do repeated flips support the expected 50% rate or a concerning higher
65% rate for a selected side? ``True`` means that selected side occurred: the
heads test uses ``is_heads`` and the tails test uses ``not is_heads``. The same
50%→65% comparison applies to either selected side.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from random import Random
from typing import Final

import pytest

from montest import Decision, sprt
from montest.pytest import CachedSamples, cached_samples, stochastic

# The expected and concerning rates apply to whichever selected side True represents.
EXPECTED_COIN_SIDE_RATE: Final = 0.50
CONCERNING_COIN_SIDE_RATE: Final = 0.65

# The two deterministic sources used to demonstrate those domain cases.
SIMULATED_FAIR_COIN_HEADS_RATE: Final = 0.50
SIMULATED_RIGGED_COIN_HEADS_RATE: Final = 0.70

# Alpha: incorrectly detecting a bias for a coin at the expected side rate. This is
# a nominal input to an approximate Wald threshold, not an observed frequency or
# exact guarantee. Lowering it requires stronger H1 evidence: fewer false alerts,
# but usually more flips/cost and possibly more inconclusive results under the finite
# cap; raising it flags sooner but tolerates more false alerts.
SPRT_ALPHA: Final = 0.05
# Beta: failing to detect a concerning side rate. This is a nominal input to an
# approximate Wald threshold, not an observed frequency or exact guarantee. Lowering
# it requires stronger H0 evidence: fewer misses, but usually more flips/cost and
# possibly more inconclusive results under the finite cap; raising it accepts the
# expected model sooner but tolerates more misses.
SPRT_BETA: Final = 0.10
MAXIMUM_FLIPS: Final = 500

NO_SELECTED_SIDE_BIAS_DETECTED: Final = Decision.ACCEPT_H0


def _bernoulli_evidence(
    expected_rate: float,
    concerning_rate: float,
) -> Callable[[bool], float]:
    """Build the statistical plumbing for one selected-side observation.

    A ``True`` observation is evidence that the selected side occurred. Its
    increment is ``log(concerning_rate / expected_rate)``. A ``False``
    observation adds ``log((1 - concerning_rate) / (1 - expected_rate))``
    instead. Thus every flip adds evidence for the expected rate or the
    concerning rate, and the accumulated evidence crosses the stopping rule's
    threshold when there is enough support for a decision.
    """
    selected_side_evidence = math.log(concerning_rate / expected_rate)
    other_side_evidence = math.log(
        (1.0 - concerning_rate) / (1.0 - expected_rate)
    )

    def evidence(is_selected_side: bool) -> float:
        return selected_side_evidence if is_selected_side else other_side_evidence

    return evidence


def detect_selected_side_bias():
    """Look for a 50%→65% increase in one selected side's rate.

    ``True`` means that the selected side happened. Therefore a caller passes
    ``is_heads`` to ask about heads and ``not is_heads`` to ask about tails;
    the same 50%→65% comparison applies to either selected side. H0 is the
    expected 50% model and H1 is the concerning 65% model. The alpha and beta
    targets guide thresholds rather than promising exact error rates. The
    finite flip budget may also end inconclusively.
    """
    return sprt(
        llr=_bernoulli_evidence(
            EXPECTED_COIN_SIDE_RATE,
            CONCERNING_COIN_SIDE_RATE,
        ),
        alpha=SPRT_ALPHA,
        beta=SPRT_BETA,
        max_samples=MAXIMUM_FLIPS,
    )


def _flip_source(*, heads_rate: float, seed: int) -> CachedSamples[bool]:
    random = Random(seed)
    return cached_samples(lambda: random.random() < heads_rate)


@pytest.fixture(scope="session")
def fair_flips() -> CachedSamples[bool]:
    """Share one fair-flip prefix so heads and tails checks replay the same flips.

    The session cache avoids a second simulated stream while keeping each test's
    cursor independent. It must not be used for a distribution with another
    heads rate.
    """
    return _flip_source(heads_rate=SIMULATED_FAIR_COIN_HEADS_RATE, seed=42)


@pytest.fixture(scope="session")
def rigged_flips() -> CachedSamples[bool]:
    """Keep the heads-biased coin separate because it has another distribution."""
    return _flip_source(heads_rate=SIMULATED_RIGGED_COIN_HEADS_RATE, seed=43)


# Expected behavior


def test_fair_coin_has_no_selected_side_bias_for_heads(
    fair_flips: CachedSamples[bool],
) -> None:
    with stochastic(fair_flips, detect_selected_side_bias()) as run:
        for is_heads in run:
            # ``True`` represents the selected heads event for this criterion.
            run.observe(is_heads)

    run.assert_decision(NO_SELECTED_SIDE_BIAS_DETECTED)


def test_fair_coin_has_no_selected_side_bias_for_tails(
    fair_flips: CachedSamples[bool],
) -> None:
    with stochastic(fair_flips, detect_selected_side_bias()) as run:
        for is_heads in run:
            # ``True`` represents the selected tails event, not raw heads.
            run.observe(not is_heads)

    run.assert_decision(NO_SELECTED_SIDE_BIAS_DETECTED)


# Known-defect demonstration


@pytest.mark.xfail(
    strict=True,
    raises=pytest.fail.Exception,
    reason=(
        "Known defect: the simulated 70% heads coin is incorrectly expected to "
        "show no selected-side bias."
    ),
)
def test_simulated_rigged_coin_has_no_selected_side_bias(
    rigged_flips: CachedSamples[bool],
) -> None:
    with stochastic(rigged_flips, detect_selected_side_bias()) as run:
        for is_heads in run:
            run.observe(is_heads)

    run.assert_decision(NO_SELECTED_SIDE_BIAS_DETECTED)
