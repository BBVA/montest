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

import asyncio
import math
import random
from collections.abc import AsyncIterator, Callable

from montest import (
    AsyncSequentialIterator,
    Decision,
    SequentialIterator,
    SPRTResult,
    sprt,
)


def bernoulli_llr(p0: float, p1: float) -> Callable[[int], float]:
    success_llr = math.log(p1 / p0)
    failure_llr = math.log((1.0 - p1) / (1.0 - p0))

    def llr(sample: int) -> float:
        return success_llr if sample else failure_llr

    return llr


def test_sync_bernoulli_h1_samples_accept_h1_before_two_hundred_samples() -> None:
    rng = random.Random(42)
    criterion = sprt(llr=bernoulli_llr(0.3, 0.6), max_samples=200)

    results = list(
        SequentialIterator(lambda: int(rng.random() < 0.6), criterion)
    )

    assert len(results) < 200
    assert results[-1].decision is Decision.ACCEPT_H1


def test_sync_bernoulli_h0_samples_accept_h0_before_two_hundred_samples() -> None:
    rng = random.Random(123)
    criterion = sprt(llr=bernoulli_llr(0.3, 0.6), max_samples=200)

    results = list(
        SequentialIterator(lambda: int(rng.random() < 0.3), criterion)
    )

    assert len(results) < 200
    assert results[-1].decision is Decision.ACCEPT_H0


async def _last_result(
    iterator: AsyncIterator[SPRTResult[int]],
) -> tuple[int, SPRTResult[int]]:
    count = 0
    last = None
    async for result in iterator:
        count += 1
        last = result
    assert last is not None
    return count, last


def test_async_bernoulli_h1_path_returns_sprt_result_and_accepts_h1() -> None:
    rng = random.Random(42)
    criterion = sprt(llr=bernoulli_llr(0.3, 0.6), max_samples=200)

    async def generate() -> int:
        return int(rng.random() < 0.6)

    count, result = asyncio.run(
        _last_result(AsyncSequentialIterator(generate, criterion, concurrency=1))
    )

    assert count < 200
    assert isinstance(result, SPRTResult)
    assert result.decision is Decision.ACCEPT_H1


def test_async_bernoulli_concurrent_path_terminates_with_terminal_decision() -> None:
    rng = random.Random(42)
    criterion = sprt(llr=bernoulli_llr(0.3, 0.6), max_samples=199)

    async def generate() -> int:
        return int(rng.random() < 0.6)

    count, result = asyncio.run(
        _last_result(AsyncSequentialIterator(generate, criterion, concurrency=4))
    )

    assert count < 200
    assert result.decision in {
        Decision.ACCEPT_H1,
        Decision.ACCEPT_H0,
        Decision.INCONCLUSIVE,
    }
