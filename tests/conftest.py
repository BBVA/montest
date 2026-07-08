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

from montest import Decision, ObservationResult


class StopAfterN:
    def __init__(
        self,
        n: int,
        *,
        decision: Decision = Decision.ACCEPT_H1,
    ) -> None:
        self._n = n
        self._decision = decision
        self._observed = 0

    def observe(self, sample: object, *, index: int) -> ObservationResult[object]:
        self._observed += 1
        decision = (
            self._decision if self._observed >= self._n else Decision.CONTINUE
        )
        return ObservationResult(value=sample, index=index, decision=decision)

    def reset(self) -> None:
        self._observed = 0
