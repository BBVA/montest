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
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from random import Random
from typing import Final
from uuid import uuid4

import pytest

from montest import ANY_OF_DECISION_MONOID, AllOf, Decision, sprt
from montest._recording import JSONValue
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

RED_NUMBERS: Final = (
    1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36
)
BLACK_NUMBERS: Final = tuple(
    number for number in range(1, 37) if number not in RED_NUMBERS
)


@dataclass(frozen=True, slots=True)
class Spin:
    number: int
    wheel_rpm: float
    ball_rpm: float
    duration_ms: int


def _color_of(number: int) -> Color:
    if not 0 <= number <= 36:
        raise ValueError("Roulette number must be between 0 and 36.")
    if number == 0:
        return Color.GREEN
    return Color.RED if number in RED_NUMBERS else Color.BLACK


def _spin_with_details(
    color_rng: Random,
    detail_rng: Random,
    red_rate: float,
    black_rate: float,
    green_rate: float,
) -> Spin:
    color = spin_roulette(color_rng, red_rate, black_rate, green_rate)
    numbers = (
        RED_NUMBERS if color is Color.RED
        else BLACK_NUMBERS if color is Color.BLACK
        else (0,)
    )
    return Spin(
        number=detail_rng.choice(numbers),
        wheel_rpm=round(detail_rng.uniform(24, 28), 1),
        ball_rpm=round(detail_rng.uniform(34, 38), 1),
        duration_ms=detail_rng.randint(4200, 6200),
    )


def _recording_options(
    request: pytest.FixtureRequest,
    scenario: str,
    seed: int,
    source_rates: tuple[float, float, float],
) -> tuple[Path | None, dict[str, JSONValue] | None]:
    directory = os.environ.get("MONTEST_RECORD_DIR")
    if not directory:
        return None, None
    return (
        Path(directory) / f"roulette-{scenario}-{uuid4().hex}.jsonl",
        {
            "test_id": request.node.nodeid,
            "scenario": scenario,
            "seed": seed,
            "source_rates": dict(
                zip(("red", "black", "green"), source_rates, strict=True)
            ),
            "h0_rates": {
                "red": EXPECTED_EUROPEAN_ROULETTE_RED_RATE,
                "black": EXPECTED_EUROPEAN_ROULETTE_BLACK_RATE,
                "green": EXPECTED_EUROPEAN_ROULETTE_GREEN_RATE,
            },
            "h1_rates": {
                "red": CONCERNING_RED_OR_BLACK_RATE,
                "black": CONCERNING_RED_OR_BLACK_RATE,
                "green": CONCERNING_GREEN_RATE,
            },
            "alpha": SPRT_ALPHA,
            "beta": SPRT_BETA,
            "max_samples": MAXIMUM_SPINS,
            "telemetry": "simulated",
        },
    )


def _spin_metadata(spin: Spin) -> dict[str, JSONValue]:
    return {
        "wheel_rpm": spin.wheel_rpm,
        "ball_rpm": spin.ball_rpm,
        "duration_ms": spin.duration_ms,
    }



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
def fair_spins() -> CachedSamples[Spin]:
    """Replay fair-wheel spins for every consumer of this one distribution."""
    color_rng = Random(42)
    detail_rng = Random(1042)
    return cached_samples(
        lambda: _spin_with_details(
            color_rng,
            detail_rng,
            SIMULATED_FAIR_RED_RATE,
            SIMULATED_FAIR_BLACK_RATE,
            SIMULATED_FAIR_GREEN_RATE,
        )
    )

@pytest.fixture(scope="session")
def rigged_spins() -> CachedSamples[Spin]:
    """Keep the rigged wheel in another cache because its color rates differ."""
    color_rng = Random(43)
    detail_rng = Random(1043)
    return cached_samples(
        lambda: _spin_with_details(
            color_rng,
            detail_rng,
            SIMULATED_RIGGED_RED_RATE,
            SIMULATED_RIGGED_BLACK_RATE,
            SIMULATED_RIGGED_GREEN_RATE,
        )
    )


# Expected behavior

def test_fair_roulette_wheel_looks_normal(
    fair_spins: CachedSamples[Spin],
    request: pytest.FixtureRequest,
) -> None:
    path, metadata = _recording_options(
        request,
        "fair",
        42,
        (
            SIMULATED_FAIR_RED_RATE,
            SIMULATED_FAIR_BLACK_RATE,
            SIMULATED_FAIR_GREEN_RATE,
        ),
    )
    with stochastic(
        fair_spins,
        detect_color_overrepresentation(),
        record_to=path,
        run_metadata=metadata,
        serialize_sample=(lambda spin: {"number": spin.number}) if path else None,
        serialize_observation=(lambda color: color.value) if path else None,
    ) as run:
        for spin in run:
            run.observe(
                _color_of(spin.number),
                metadata=_spin_metadata(spin) if path else None,
            )

    run.assert_decision(NO_OVERREPRESENTED_COLOR_DETECTED)


# Known-defect demonstration
@pytest.mark.xfail(
    strict=True,
    raises=pytest.fail.Exception,
    reason="A rigged wheel violates the no-overrepresented-color requirement.",
)
def test_rigged_roulette_wheel_violates_no_overrepresented_color_requirement(
    rigged_spins: CachedSamples[Spin],
    request: pytest.FixtureRequest,
) -> None:
    path, metadata = _recording_options(
        request,
        "rigged",
        43,
        (
            SIMULATED_RIGGED_RED_RATE,
            SIMULATED_RIGGED_BLACK_RATE,
            SIMULATED_RIGGED_GREEN_RATE,
        ),
    )
    with stochastic(
        rigged_spins,
        detect_color_overrepresentation(),
        record_to=path,
        run_metadata=metadata,
        serialize_sample=(lambda spin: {"number": spin.number}) if path else None,
        serialize_observation=(lambda color: color.value) if path else None,
    ) as run:
        for spin in run:
            run.observe(
                _color_of(spin.number),
                metadata=_spin_metadata(spin) if path else None,
            )

    run.assert_decision(NO_OVERREPRESENTED_COLOR_DETECTED)
