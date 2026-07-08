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

from collections.abc import Callable, Iterator
from typing import Generic, TypeVar

from montest._criterion import StoppingCriterion
from montest._types import Decision, ObservationResult

S = TypeVar("S")
R = TypeVar("R", bound=ObservationResult[object])


class SequentialIterator(Generic[S, R], Iterator[R]):
    def __init__(
        self,
        generate: Callable[[], S],
        criterion: StoppingCriterion[S, R],
    ) -> None:
        self._generate = generate
        self._criterion = criterion
        self._index = 0
        self._stopped = False

    def __iter__(self) -> SequentialIterator[S, R]:
        return self

    def __next__(self) -> R:
        if self._stopped:
            raise StopIteration

        value = self._generate()
        result = self._criterion.observe(value, index=self._index)
        self._index += 1

        if result.decision is not Decision.CONTINUE:
            self._stopped = True

        return result
