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
#
# ruff: noqa: E501
"""Copyable tests for whether either die has a meaningful high-roll bias.

Question: does a colored pair look normal, or is either die rolling 4--6 often
enough to be concerning? Each raw pair becomes two high-roll observations, then
the pair-level decision stops when the evidence is sufficient.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from random import Random
from typing import Final

import pytest

from montest import AnyOf, Decision, sprt
from montest.pytest import CachedSamples, cached_samples, stochastic

# The criterion models a fair die as P(roll >= 4) = .50 and flags .58 or more.
EXPECTED_FAIR_DIE_HIGH_ROLL_RATE: Final = 0.50
CONCERNING_DIE_HIGH_ROLL_RATE: Final = 0.58

# These source truths are intentionally separate from the criterion hypotheses.
# The fair and loaded source constants stay distinct even when a value coincides.
SIMULATED_FAIR_DIE_HIGH_ROLL_RATE: Final = 0.50
SIMULATED_LOADED_YELLOW_HIGH_ROLL_RATE: Final = 0.65

# False alarm: calling a fair color's die loaded/overrepresented. This is a nominal
# input to an approximate Wald threshold, not an observed frequency or exact guarantee.
# Lowering it requires stronger H1 evidence: fewer false alerts, but usually more
# pairs/cost and possibly more inconclusive results under the finite cap; raising it
# flags sooner but tolerates more false alerts.
SPRT_ALPHA: Final = 0.05
# Miss: calling a truly loaded/overrepresented color's die normal. This is a nominal
# input to an approximate Wald threshold, not an observed frequency or exact guarantee.
# Lowering it requires stronger H0 evidence: fewer misses, but usually more
# pairs/cost and possibly more inconclusive results under the finite cap; raising it
# accepts normal sooner but tolerates more misses.
SPRT_BETA: Final = 0.10
# Each yellow/violet child gets these targets; the composite pair's error behavior
# differs, and it has no multiple-testing correction.
MAXIMUM_PAIR_ROLLS: Final = 500

NO_LOADED_DIE_DETECTED: Final = Decision.ACCEPT_H0


@dataclass(frozen=True, slots=True)
class Roll:
    """The raw outcomes of one yellow/violet dice-pair roll."""

    yellow: int
    violet: int


@dataclass(frozen=True, slots=True)
class HighRolls:
    """The high-roll booleans derived from one raw yellow/violet outcome."""

    yellow: bool
    violet: bool


def roll_die(rng: Random, high_roll_rate: float) -> int:
    """Roll 4--6 with ``high_roll_rate`` and 1--3 otherwise."""
    if rng.random() < high_roll_rate:
        return rng.choice([4, 5, 6])
    return rng.choice([1, 2, 3])

def is_high(value: int) -> bool:
    """Say whether one die's raw face is the modeled 4--6 high-roll event."""
    return value >= 4


def high_rolls(roll: Roll) -> HighRolls:
    """Turn one raw pair into the two ``is_high`` observations we model."""
    return HighRolls(yellow=is_high(roll.yellow), violet=is_high(roll.violet))


def _high_roll_evidence(
    normal_rate: float,
    concerning_rate: float,
) -> Callable[[bool], float]:
    """Build statistical plumbing for one die's ``is_high`` observation.

    ``True`` means that die rolled 4--6. It adds
    ``log(concerning_rate / normal_rate)`` evidence; ``False`` adds
    ``log((1 - concerning_rate) / (1 - normal_rate))``. Accumulated evidence
    crosses a threshold for the normal or concerning high-roll behavior.
    """
    high_roll_evidence = math.log(concerning_rate / normal_rate)
    low_roll_evidence = math.log(
        (1.0 - concerning_rate) / (1.0 - normal_rate)
    )

    def evidence(is_high: bool) -> float:
        return high_roll_evidence if is_high else low_roll_evidence

    return evidence


def detect_either_die_high_roll_bias() -> AnyOf[HighRolls]:
    """Decide whether a colored pair has a materially high-roll-biased die.

    Each die is expected fair at ``EXPECTED_FAIR_DIE_HIGH_ROLL_RATE`` and
    concerning at ``CONCERNING_DIE_HIGH_ROLL_RATE``. ``AnyOf`` models the
    pair-level rule: either yellow or violet being biased is enough to flag the
    pair. Only after that domain rule, the statistical names are H0 for both dice
    looking normal and H1 for either die looking concerning. Nominal false-alarm
    and miss targets guide thresholds; the finite pair budget can be inconclusive.
    """
    evidence = _high_roll_evidence(
        EXPECTED_FAIR_DIE_HIGH_ROLL_RATE,
        CONCERNING_DIE_HIGH_ROLL_RATE,
    )
    return AnyOf(
        {
            "yellow": sprt(
                llr=lambda pair: evidence(pair.yellow),
                alpha=SPRT_ALPHA,
                beta=SPRT_BETA,
                max_samples=MAXIMUM_PAIR_ROLLS,
            ),
            "violet": sprt(
                llr=lambda pair: evidence(pair.violet),
                alpha=SPRT_ALPHA,
                beta=SPRT_BETA,
                max_samples=MAXIMUM_PAIR_ROLLS,
            ),
        }
    )


@pytest.fixture(scope="session")
def fair_rolls() -> CachedSamples[Roll]:
    """Replay fair pairs across tests instead of making another fair sequence."""
    rng = Random(42)
    return cached_samples(
        lambda: Roll(
            yellow=roll_die(rng, SIMULATED_FAIR_DIE_HIGH_ROLL_RATE),
            violet=roll_die(rng, SIMULATED_FAIR_DIE_HIGH_ROLL_RATE),
        )
    )


@pytest.fixture(scope="session")
def loaded_rolls() -> CachedSamples[Roll]:
    """Use another cache because the yellow die has another distribution."""
    rng = Random(43)
    return cached_samples(
        lambda: Roll(
            yellow=roll_die(rng, SIMULATED_LOADED_YELLOW_HIGH_ROLL_RATE),
            violet=roll_die(rng, SIMULATED_FAIR_DIE_HIGH_ROLL_RATE),
        )
    )


# Expected behavior

def test_fair_dice_pair_looks_normal(fair_rolls: CachedSamples[Roll]) -> None:
    with stochastic(fair_rolls, detect_either_die_high_roll_bias()) as run:
        for roll in run:
            # Roll -> HighRolls gives each AnyOf child its own ``is_high`` value.
            run.observe(high_rolls(roll))

    run.assert_decision(NO_LOADED_DIE_DETECTED)


# Known-defect demonstration
@pytest.mark.xfail(
    strict=True,
    raises=pytest.fail.Exception,
    reason="Known defect: the loaded yellow die reaches an H1 decision.",
)
def test_loaded_yellow_die_is_not_detected(
    loaded_rolls: CachedSamples[Roll],
) -> None:
    with stochastic(loaded_rolls, detect_either_die_high_roll_bias()) as run:
        for roll in run:
            run.observe(high_rolls(roll))

    run.assert_decision(NO_LOADED_DIE_DETECTED)

