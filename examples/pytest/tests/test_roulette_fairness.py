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

"""Copyable tests for meaningful departures from European roulette odds.

Question: does a wheel look normal, or is any color appearing often enough to
be concerning? Every spin supplies color-match observations; the stopping
decision reports whether the wheel as a whole looks normal or color-biased.
"""

from __future__ import annotations

import enum
import math
from collections.abc import Callable
from random import Random
from typing import Final

import pytest

from montest import ANY_OF_DECISION_MONOID, AllOf, Decision, sprt
from montest.pytest import CachedSamples, cached_samples, stochastic

EXPECTED_EUROPEAN_ROULETTE_RED_RATE: Final = 18 / 37
EXPECTED_EUROPEAN_ROULETTE_BLACK_RATE: Final = 18 / 37
EXPECTED_EUROPEAN_ROULETTE_GREEN_RATE: Final = 1 / 37
CONCERNING_RED_OR_BLACK_RATE: Final = 0.55
CONCERNING_GREEN_RATE: Final = 0.08

SIMULATED_FAIR_RED_RATE: Final = 18 / 37
SIMULATED_FAIR_BLACK_RATE: Final = 18 / 37
SIMULATED_FAIR_GREEN_RATE: Final = 1 / 37
SIMULATED_RIGGED_RED_RATE: Final = 0.45
SIMULATED_RIGGED_BLACK_RATE: Final = 0.45
SIMULATED_RIGGED_GREEN_RATE: Final = 0.10

# False alarm: calling a fair wheel color overrepresented. This is a nominal input
# to an approximate Wald threshold, not an observed frequency or exact guarantee.
# Lowering it requires stronger H1 evidence: fewer false alerts, but usually more
# spins/cost and possibly more inconclusive results under the finite cap; raising it
# flags sooner but tolerates more false alerts.
SPRT_ALPHA: Final = 0.05
# Miss: calling a truly overrepresented wheel color normal. This is a nominal input
# to an approximate Wald threshold, not an observed frequency or exact guarantee.
# Lowering it requires stronger H0 evidence: fewer misses, but usually more
# spins/cost and possibly more inconclusive results under the finite cap; raising it
# accepts normal sooner but tolerates more misses.
SPRT_BETA: Final = 0.10
# Each red/black/green child gets these targets; the composite wheel's error behavior
# differs, and it has no multiple-testing correction.
MAXIMUM_SPINS: Final = 500

NO_OVERREPRESENTED_COLOR_DETECTED: Final = Decision.ACCEPT_H0


class Color(enum.Enum):
    RED = "red"
    BLACK = "black"
    GREEN = "green"


def spin_roulette(
    rng: Random,
    red_rate: float,
    black_rate: float,
    green_rate: float,
) -> Color:
    """Return a roulette color sampled from a validated complete distribution."""
    if min(red_rate, black_rate, green_rate) < 0:
        raise ValueError("Roulette color rates must be non-negative.")
    if not math.isclose(
        red_rate + black_rate + green_rate,
        1.0,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ValueError("Roulette color rates must sum to 1.")

    value = rng.random()
    if value < red_rate:
        return Color.RED
    if value < red_rate + black_rate:
        return Color.BLACK
    return Color.GREEN


def _color_match_evidence(
    tracked_color: Color,
    normal_rate: float,
    concerning_rate: float,
) -> Callable[[Color], float]:
    """Build statistical plumbing for whether a spin matches one color.

    A matching spin adds ``log(concerning_rate / normal_rate)`` evidence. A
    non-matching spin adds
    ``log((1 - concerning_rate) / (1 - normal_rate))`` instead. In these
    formulas, ``normal_rate`` is the expected European color rate and
    ``concerning_rate`` is the rate worth flagging. Accumulated evidence crosses
    a threshold for normal or concerning behavior.
    """
    match_evidence = math.log(concerning_rate / normal_rate)
    non_match_evidence = math.log(
        (1.0 - concerning_rate) / (1.0 - normal_rate)
    )

    def evidence(spin: Color) -> float:
        return match_evidence if spin is tracked_color else non_match_evidence

    return evidence


def detect_color_overrepresentation() -> AllOf[Color]:
    """Assess whether any European-wheel color occurs materially too often.

    Red and black normally occur at their European rates, while green normally
    occurs at its smaller European rate; each child compares that behavior with
    its named concerning rate above. ``AllOf`` waits for every color child to
    finish, so all colors receive evidence. Its ``ANY_OF`` resolver still calls
    the wheel color-biased when any color is overrepresented. In statistical
    terms only, the all-normal behavior is H0 and any overrepresentation is H1.
    Nominal false-alarm and miss targets guide thresholds, and the finite spin
    budget can terminate inconclusively.
    """
    return AllOf(
        {
            "red": sprt(
                llr=_color_match_evidence(
                    Color.RED,
                    EXPECTED_EUROPEAN_ROULETTE_RED_RATE,
                    CONCERNING_RED_OR_BLACK_RATE,
                ),
                alpha=SPRT_ALPHA,
                beta=SPRT_BETA,
                max_samples=MAXIMUM_SPINS,
            ),
            "black": sprt(
                llr=_color_match_evidence(
                    Color.BLACK,
                    EXPECTED_EUROPEAN_ROULETTE_BLACK_RATE,
                    CONCERNING_RED_OR_BLACK_RATE,
                ),
                alpha=SPRT_ALPHA,
                beta=SPRT_BETA,
                max_samples=MAXIMUM_SPINS,
            ),
            "green": sprt(
                llr=_color_match_evidence(
                    Color.GREEN,
                    EXPECTED_EUROPEAN_ROULETTE_GREEN_RATE,
                    CONCERNING_GREEN_RATE,
                ),
                alpha=SPRT_ALPHA,
                beta=SPRT_BETA,
                max_samples=MAXIMUM_SPINS,
            ),
        },
        resolve=ANY_OF_DECISION_MONOID.resolve,
    )


@pytest.fixture(scope="session")
def fair_spins() -> CachedSamples[Color]:
    """Replay fair-wheel spins for every consumer of this one distribution."""
    rng = Random(42)
    return cached_samples(
        lambda: spin_roulette(
            rng,
            SIMULATED_FAIR_RED_RATE,
            SIMULATED_FAIR_BLACK_RATE,
            SIMULATED_FAIR_GREEN_RATE,
        )
    )


@pytest.fixture(scope="session")
def rigged_spins() -> CachedSamples[Color]:
    """Keep the rigged wheel in another cache because its color rates differ."""
    rng = Random(43)
    return cached_samples(
        lambda: spin_roulette(
            rng,
            SIMULATED_RIGGED_RED_RATE,
            SIMULATED_RIGGED_BLACK_RATE,
            SIMULATED_RIGGED_GREEN_RATE,
        )
    )


# Expected behavior

def test_fair_roulette_wheel_looks_normal(
    fair_spins: CachedSamples[Color],
) -> None:
    with stochastic(fair_spins, detect_color_overrepresentation()) as run:
        for spin in run:
            # Each spin becomes red/black/green color-match evidence in the children.
            run.observe(spin)

    run.assert_decision(NO_OVERREPRESENTED_COLOR_DETECTED)


# Known-defect demonstration
@pytest.mark.xfail(
    strict=True,
    raises=pytest.fail.Exception,
    reason="A rigged wheel violates the no-overrepresented-color requirement.",
)
def test_rigged_roulette_wheel_violates_no_overrepresented_color_requirement(
    rigged_spins: CachedSamples[Color],
) -> None:
    with stochastic(rigged_spins, detect_color_overrepresentation()) as run:
        for spin in run:
            run.observe(spin)

    run.assert_decision(NO_OVERREPRESENTED_COLOR_DETECTED)
