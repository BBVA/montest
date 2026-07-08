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
import inspect
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Generic, TypeAlias, TypeVar, cast

from montest._criterion import StoppingCriterion
from montest._types import Decision, ObservationResult

S = TypeVar("S")
R = TypeVar("R", bound=ObservationResult[object])
GenerateFn: TypeAlias = Callable[[], S] | Callable[[], Awaitable[S]]


class AsyncSequentialIterator(Generic[S, R], AsyncIterator[R]):
    def __init__(
        self,
        generate: GenerateFn[S],
        criterion: StoppingCriterion[S, R],
        concurrency: int = 1,
    ) -> None:
        if concurrency < 1:
            raise ValueError(f"concurrency must be >= 1, got {concurrency}")

        self._generate = generate
        self._criterion = criterion
        self._concurrency = concurrency
        self._index = 0
        self._stopped = False
        self._pending: deque[R] = deque()
        self._is_async_generate = inspect.iscoroutinefunction(generate)

    def __aiter__(self) -> AsyncSequentialIterator[S, R]:
        return self

    async def __anext__(self) -> R:
        if self._pending:
            return self._pending.popleft()

        if self._stopped:
            raise StopAsyncIteration

        values = await asyncio.gather(
            *(self._generate_one() for _ in range(self._concurrency))
        )
        for value in values:
            result = self._criterion.observe(value, index=self._index)
            self._index += 1
            self._pending.append(result)
            if result.decision is not Decision.CONTINUE:
                self._stopped = True
                break

        if self._pending:
            return self._pending.popleft()

        raise StopAsyncIteration

    async def _generate_one(self) -> S:
        if self._is_async_generate:
            result = self._generate()
            return await cast(Awaitable[S], result)

        generate = cast(Callable[[], S], self._generate)
        return await asyncio.to_thread(generate)
