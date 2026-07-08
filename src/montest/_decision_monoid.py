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

import dataclasses
from collections.abc import Mapping, Sequence

from montest._types import Decision


@dataclasses.dataclass(frozen=True, slots=True)
class DecisionMonoid:
    identity: Decision
    _rank: Mapping[Decision, int]

    def combine(self, left: Decision, right: Decision) -> Decision:
        if self._rank[left] >= self._rank[right]:
            return left
        return right

    def resolve(self, decisions: Sequence[Decision]) -> Decision:
        result = self.identity
        for decision in decisions:
            result = self.combine(result, decision)
        return result


ANY_OF_DECISION_MONOID = DecisionMonoid(
    identity=Decision.ACCEPT_H0,
    _rank={
        Decision.ACCEPT_H0: 0,
        Decision.INCONCLUSIVE: 1,
        Decision.ACCEPT_H1: 2,
    },
)

ALL_OF_DECISION_MONOID = DecisionMonoid(
    identity=Decision.ACCEPT_H1,
    _rank={
        Decision.ACCEPT_H1: 0,
        Decision.INCONCLUSIVE: 1,
        Decision.ACCEPT_H0: 2,
    },
)
