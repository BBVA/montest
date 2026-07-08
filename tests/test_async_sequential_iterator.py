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
from collections.abc import AsyncIterator
from itertools import count

import pytest

from montest import AsyncSequentialIterator, Decision, ObservationResult
from tests.conftest import StopAfterN


async def _collect(
    iterator: AsyncIterator[ObservationResult[object]],
) -> list[ObservationResult[object]]:
    return [result async for result in iterator]


def test_async_iterator_yields_exact_count_with_default_concurrency() -> None:
    values = count()
    results = asyncio.run(
        _collect(AsyncSequentialIterator(lambda: next(values), StopAfterN(3)))
    )

    assert [result.value for result in results] == [0, 1, 2]
    assert [result.index for result in results] == [0, 1, 2]
    assert [result.decision for result in results[:-1]] == [
        Decision.CONTINUE,
        Decision.CONTINUE,
    ]
    assert results[-1].decision is Decision.ACCEPT_H1


def test_async_sequential_iterator_accepts_async_generator_function() -> None:
    calls = 0

    async def generate() -> int:
        nonlocal calls
        calls += 1
        return calls

    results = asyncio.run(_collect(AsyncSequentialIterator(generate, StopAfterN(2))))

    assert [result.value for result in results] == [1, 2]
    assert results[-1].decision is Decision.ACCEPT_H1


def test_async_sequential_iterator_accepts_sync_generator_function() -> None:
    values = count(10)

    results = asyncio.run(
        _collect(AsyncSequentialIterator(lambda: next(values), StopAfterN(2)))
    )

    assert [result.value for result in results] == [10, 11]
    assert results[-1].decision is Decision.ACCEPT_H1


def test_async_sequential_iterator_rejects_non_positive_concurrency() -> None:
    with pytest.raises(ValueError, match="concurrency"):
        AsyncSequentialIterator(lambda: object(), StopAfterN(1), concurrency=0)


def test_async_sequential_iterator_discards_surplus_batch_results() -> None:
    calls = 0

    async def generate() -> int:
        nonlocal calls
        calls += 1
        return calls

    results = asyncio.run(
        _collect(AsyncSequentialIterator(generate, StopAfterN(3), concurrency=4))
    )

    assert [result.value for result in results] == [1, 2, 3]
    assert [result.index for result in results] == [0, 1, 2]
    assert results[-1].decision is Decision.ACCEPT_H1
    assert calls == 4
