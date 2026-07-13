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

"""Live Gemini tests for expected and known-defect emoji-rate behavior.

``ACCEPT_H0`` supports the configured 5% emoji-rate model over the 70%
alternative; it does not prove zero emoji or absolute compliance. These live
tests require credentials and xfail when no key is available.
"""

from __future__ import annotations

import math
import os
import re
import time
from collections.abc import Callable
from typing import Final

import pytest
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from montest import Decision, sprt
from montest.pytest import CachedSamples, cached_samples, stochastic

# These are the low- and concerning-high emoji-rate models compared by the
# criterion.
LOW_EMOJI_REFERENCE_RATE: Final = 0.05
CONCERNING_HIGH_EMOJI_RATE: Final = 0.70

# Alpha is the nominal false-alarm target: calling a low-emoji stream
# high-emoji. It constructs an approximate Wald threshold rather than an exact
# guarantee. Lower alpha requires stronger H1 evidence, which can increase
# response cost and finite-budget inconclusive results.
SPRT_ALPHA: Final = 0.05
# Beta is the nominal miss target: calling a truly high-emoji stream low-emoji.
# It constructs an approximate Wald threshold rather than an exact guarantee.
# Lower beta requires stronger H0 evidence, which can increase response cost and
# finite-budget inconclusive results.
SPRT_BETA: Final = 0.10
MAXIMUM_RESPONSES: Final = 50

LOW_EMOJI_RATE_SUPPORTED: Final = Decision.ACCEPT_H0

KNOWN_BAD_PROMPT_WITHOUT_EMOJI_CONTROL: Final = (
    "You are a friendly and enthusiastic store clerk at a trendy gadget shop. "
    "You love helping customers find the perfect product and you express your "
    "excitement naturally. Be brief."
)
NO_EMOJI_SYSTEM_PROMPT: Final = (
    "You are a friendly and enthusiastic store clerk at a trendy gadget shop. "
    "You love helping customers find the perfect product and you express your "
    "excitement naturally. Be brief.\n\n"
    "IMPORTANT: You must NEVER use any emoji characters in your responses. "
    "Express yourself using only plain text words and punctuation."
)
USER_REQUEST: Final = (
    "Hey! I'm looking for a gift for my friend who loves cooking. "
    "Do you have any cool kitchen gadgets? My budget is around $50."
)
GEMINI_MODEL: Final = "gemini-2.5-flash-lite"

_EMOJI_PATTERN = re.compile(
    "["
    "\U0001f600-\U0001f64f"  # emoticons
    "\U0001f300-\U0001f5ff"  # misc symbols & pictographs
    "\U0001f680-\U0001f6ff"  # transport & map
    "\U0001f1e0-\U0001f1ff"  # flags
    "\U00002702-\U000027b0"  # dingbats
    "\U0001f900-\U0001f9ff"  # supplemental symbols
    "\U0001fa00-\U0001fa6f"  # chess, extended-A
    "\U0001fa70-\U0001faff"  # extended-A continued
    "\U00002600-\U000026ff"  # misc symbols
    "\U0000fe00-\U0000fe0f"  # variation selectors
    "\U0000200d"  # ZWJ
    "]"
)


def contains_emoji(text: str) -> bool:
    """Turn a raw model response into the ``contains_emoji`` observation."""
    return bool(_EMOJI_PATTERN.search(text))


def _emoji_presence_evidence(
    low_rate: float,
    high_rate: float,
) -> Callable[[bool], float]:
    """Build evidence for one ``contains_emoji`` observation.

    A response containing emoji adds ``log(high_rate / low_rate)`` evidence.
    A response without emoji adds ``log((1 - high_rate) / (1 - low_rate))``.
    Accumulated evidence distinguishes the configured low- and high-frequency
    models.
    """
    emoji_evidence = math.log(high_rate / low_rate)
    plain_text_evidence = math.log((1.0 - high_rate) / (1.0 - low_rate))

    def evidence(contains_emoji: bool) -> float:
        return emoji_evidence if contains_emoji else plain_text_evidence

    return evidence


def detect_high_emoji_frequency():
    """Compare the 5% reference and 70% concerning emoji-rate models.

    H0 is the 5% reference model and H1 is the 70% concerning model. An
    ``ACCEPT_H0`` result supports the 5% model over this alternative; it does
    not prove that responses contain zero emoji or establish absolute compliance.
    Alpha and beta construct approximate Wald thresholds, while the finite
    response budget can finish inconclusively.
    """
    return sprt(
        llr=_emoji_presence_evidence(
            LOW_EMOJI_REFERENCE_RATE,
            CONCERNING_HIGH_EMOJI_RATE,
        ),
        alpha=SPRT_ALPHA,
        beta=SPRT_BETA,
        max_samples=MAXIMUM_RESPONSES,
    )


def _api_key() -> str:
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if api_key is None:
        raise RuntimeError("LLM example requires GOOGLE_API_KEY or GEMINI_API_KEY.")
    return api_key


def make_llm_caller(
    *,
    client: genai.Client,
    system_prompt: str,
) -> Callable[[], str]:
    """Make one Gemini caller that retries transient server failures only."""

    def call() -> str:
        for attempt in range(5):
            try:
                response = client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=USER_REQUEST,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=1.0,
                    ),
                )
            except genai_errors.ServerError:
                if attempt == 4:
                    raise
                time.sleep(float(2**attempt))
            else:
                return response.text or ""
        raise AssertionError("unreachable")

    return call


def _live_source(system_prompt: str) -> Callable[[], str]:
    client = genai.Client(api_key=_api_key())
    return make_llm_caller(client=client, system_prompt=system_prompt)


@pytest.fixture(scope="session")
def no_emoji_responses() -> CachedSamples[str]:
    """Cache the controlled prompt's responses for expected behavior."""
    return cached_samples(_live_source(NO_EMOJI_SYSTEM_PROMPT))


@pytest.fixture(scope="session")
def missing_emoji_control_responses() -> CachedSamples[str]:
    """Use a separate cache because this prompt changes the response model."""
    return cached_samples(_live_source(KNOWN_BAD_PROMPT_WITHOUT_EMOJI_CONTROL))


_MISSING_CREDENTIALS_REASON: Final = (
    "LLM example requires GOOGLE_API_KEY or GEMINI_API_KEY."
)
_HAS_LIVE_CREDENTIALS: Final = bool(
    os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
)


# Expected behavior
@pytest.mark.xfail(
    not _HAS_LIVE_CREDENTIALS,
    reason=_MISSING_CREDENTIALS_REASON,
)
def test_no_emoji_prompt_supports_low_emoji_rate(
    no_emoji_responses: CachedSamples[str],
) -> None:
    with stochastic(no_emoji_responses, detect_high_emoji_frequency()) as run:
        for response in run:
            run.observe(contains_emoji(response))

    run.assert_decision(LOW_EMOJI_RATE_SUPPORTED)


# Known-defect demonstration
@pytest.mark.xfail(
    strict=True,
    raises=pytest.fail.Exception,
    reason=(
        "Known defect: the prompt without an emoji control must not support "
        "the low emoji-rate model."
    ),
)
@pytest.mark.xfail(
    not _HAS_LIVE_CREDENTIALS,
    reason=_MISSING_CREDENTIALS_REASON,
)
def test_missing_emoji_control_does_not_support_low_emoji_rate(
    missing_emoji_control_responses: CachedSamples[str],
) -> None:
    with stochastic(
        missing_emoji_control_responses,
        detect_high_emoji_frequency(),
    ) as run:
        for response in run:
            run.observe(contains_emoji(response))

    run.assert_decision(LOW_EMOJI_RATE_SUPPORTED)


