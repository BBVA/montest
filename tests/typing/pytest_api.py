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

from collections.abc import Iterator
from dataclasses import dataclass
from typing import assert_type

from montest import Decision, ObservationResult
from montest.pytest import CachedSamples, StochasticRun, cached_samples, stochastic


@dataclass(frozen=True, slots=True)
class LabelledResult(ObservationResult[str]):
    """A result type intentionally distinct from raw and observed values."""


class LengthCriterion:
    def observe(self, observation: int, *, index: int) -> LabelledResult:
        return LabelledResult(
            value=f"length={observation}",
            index=index,
            decision=Decision.ACCEPT_H0,
        )

    def reset(self) -> None:
        pass


def produce_raw() -> bytes:
    return b"sample"


source = CachedSamples(produce_raw)
source_from_factory = cached_samples(produce_raw)
criterion = LengthCriterion()

direct_run = StochasticRun(source, criterion)
factory_run = stochastic(source_from_factory, criterion)

assert_type(source, CachedSamples[bytes])
assert_type(source_from_factory, CachedSamples[bytes])
assert_type(iter(source), Iterator[bytes])
assert_type(direct_run, StochasticRun[bytes, int, LabelledResult])
assert_type(factory_run, StochasticRun[bytes, int, LabelledResult])
assert_type(direct_run.observe(6), LabelledResult)
assert_type(direct_run.result, LabelledResult)
