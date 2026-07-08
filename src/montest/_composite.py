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
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Generic, TypeVar, cast

from montest._criterion import StoppingCriterion
from montest._decision_monoid import (
    ALL_OF_DECISION_MONOID,
    ANY_OF_DECISION_MONOID,
)
from montest._types import Decision, ObservationResult

S = TypeVar("S")

@dataclasses.dataclass(frozen=True, slots=True)
class CompositeResult(ObservationResult[S], Generic[S]):
    results: Mapping[str, ObservationResult[S] | None]
    n_decided: int
    n_total: int


class _CompositeBase(Generic[S]):
    def __init__(
        self,
        criteria: Mapping[str, StoppingCriterion[S, ObservationResult[Any]]],
        *,
        resolve: Callable[[Sequence[Decision]], Decision],
    ) -> None:
        if not criteria:
            raise ValueError("criteria must not be empty")
        if any(not isinstance(key, str) or not key for key in criteria):
            raise ValueError("criterion keys must be non-empty strings")

        self._criteria = dict(criteria)
        self._resolve = resolve
        self._terminal_decisions: dict[str, Decision] = {}
        self._terminal = False

    def reset(self) -> None:
        for criterion in self._criteria.values():
            criterion.reset()
        self._terminal_decisions.clear()
        self._terminal = False

    def _terminal_decision_sequence(self) -> list[Decision]:
        return [
            self._terminal_decisions[key]
            for key in self._criteria
            if key in self._terminal_decisions
        ]

    def _result(
        self,
        *,
        sample: S,
        index: int,
        decision: Decision,
        results: Mapping[str, ObservationResult[Any] | None],
        n_decided: int,
    ) -> CompositeResult[S]:
        return CompositeResult(
            value=sample,
            index=index,
            decision=decision,
            results=cast(Mapping[str, ObservationResult[S] | None], dict(results)),
            n_decided=n_decided,
            n_total=len(self._criteria),
        )

    def _ensure_running(self) -> None:
        if self._terminal:
            raise RuntimeError(
                "Criterion already reached a decision; call reset() first."
            )


class AllOf(_CompositeBase[S]):
    def __init__(
        self,
        criteria: Mapping[str, StoppingCriterion[S, ObservationResult[Any]]],
        *,
        resolve: Callable[[Sequence[Decision]], Decision] | None = None,
    ) -> None:
        super().__init__(
            criteria,
            resolve=resolve or ALL_OF_DECISION_MONOID.resolve,
        )

    def observe(self, sample: S, *, index: int) -> CompositeResult[S]:
        self._ensure_running()

        results: dict[str, ObservationResult[Any] | None] = {}
        for key, criterion in self._criteria.items():
            if key in self._terminal_decisions:
                results[key] = None
                continue

            result = criterion.observe(sample, index=index)
            results[key] = result
            if result.decision is not Decision.CONTINUE:
                self._terminal_decisions[key] = result.decision

        n_decided = len(self._terminal_decisions)
        decision = Decision.CONTINUE
        if n_decided == len(self._criteria):
            decision = self._resolve(self._terminal_decision_sequence())
            self._terminal = True

        return self._result(
            sample=sample,
            index=index,
            decision=decision,
            results=results,
            n_decided=n_decided,
        )


class AnyOf(_CompositeBase[S]):
    def __init__(
        self,
        criteria: Mapping[str, StoppingCriterion[S, ObservationResult[Any]]],
        *,
        resolve: Callable[[Sequence[Decision]], Decision] | None = None,
    ) -> None:
        super().__init__(
            criteria,
            resolve=resolve or ANY_OF_DECISION_MONOID.resolve,
        )

    def observe(self, sample: S, *, index: int) -> CompositeResult[S]:
        self._ensure_running()

        results: dict[str, ObservationResult[Any] | None] = {}
        stopped_early = False
        for key, criterion in self._criteria.items():
            if key in self._terminal_decisions:
                results[key] = None
                continue

            if stopped_early:
                results[key] = None
                continue

            result = criterion.observe(sample, index=index)
            results[key] = result
            if result.decision is Decision.CONTINUE:
                continue

            self._terminal_decisions[key] = result.decision
            if result.decision is Decision.ACCEPT_H1:
                stopped_early = True

        n_total = len(self._criteria)
        n_decided = len(self._terminal_decisions)
        decision = Decision.CONTINUE
        if stopped_early:
            decision = self._resolve(self._terminal_decision_sequence())
            n_decided = n_total
            self._terminal = True
        elif n_decided == n_total:
            decision = self._resolve(self._terminal_decision_sequence())
            self._terminal = True

        return self._result(
            sample=sample,
            index=index,
            decision=decision,
            results=results,
            n_decided=n_decided,
        )
