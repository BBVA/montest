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

from itertools import count

import pytest
from hypothesis import given
from hypothesis import strategies as st

from montest import Decision, SequentialIterator
from tests.conftest import StopAfterN


def test_sequential_iterator_yields_terminal_result_once_then_stops() -> None:
    values = count()
    iterator = SequentialIterator(
        lambda: next(values),
        StopAfterN(4, decision=Decision.ACCEPT_H0),
    )

    results = [next(iterator), next(iterator), next(iterator), next(iterator)]

    assert [result.value for result in results] == [0, 1, 2, 3]
    assert [result.index for result in results] == [0, 1, 2, 3]
    assert [result.decision for result in results[:-1]] == [
        Decision.CONTINUE,
        Decision.CONTINUE,
        Decision.CONTINUE,
    ]
    assert results[-1].decision is Decision.ACCEPT_H0
    with pytest.raises(StopIteration):
        next(iterator)


@given(st.integers(min_value=1, max_value=200))
def test_sequential_iterator_yield_count_matches_stopping_boundary(n: int) -> None:
    results = list(SequentialIterator(lambda: object(), StopAfterN(n)))

    assert len(results) == n
    assert results[-1].decision is not Decision.CONTINUE
