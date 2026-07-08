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

import math
from collections.abc import Callable
from typing import Generic, TypeVar

from montest._types import Decision
from montest.algorithms.sprt._result import SPRTResult

S = TypeVar("S")


class SPRT(Generic[S]):
    def __init__(
        self,
        *,
        llr: Callable[[S], float],
        alpha: float = 0.05,
        beta: float = 0.10,
        max_samples: int | None = None,
    ) -> None:
        if not (0.0 < alpha < 1.0):
            raise ValueError(f"alpha must be in (0, 1), got {alpha}")
        if not (0.0 < beta < 1.0):
            raise ValueError(f"beta must be in (0, 1), got {beta}")
        if max_samples is not None and max_samples < 1:
            raise ValueError(f"max_samples must be >= 1, got {max_samples}")

        self._llr = llr
        self._max_samples = max_samples
        self._lower = math.log(beta / (1.0 - alpha))
        self._upper = math.log((1.0 - beta) / alpha)
        self._cumulative_llr = 0.0
        self._n_observed = 0
        self._terminal = False

    @property
    def lower_bound(self) -> float:
        return self._lower

    @property
    def upper_bound(self) -> float:
        return self._upper

    @property
    def cumulative_llr(self) -> float:
        return self._cumulative_llr

    @property
    def n_observed(self) -> int:
        return self._n_observed

    def observe(self, sample: S, *, index: int) -> SPRTResult[S]:
        if self._terminal:
            raise RuntimeError(
                "Criterion already reached a decision; call reset() first."
            )

        self._n_observed += 1
        self._cumulative_llr += self._llr(sample)

        decision = Decision.CONTINUE
        if self._cumulative_llr >= self._upper:
            decision = Decision.ACCEPT_H1
        elif self._cumulative_llr <= self._lower:
            decision = Decision.ACCEPT_H0
        elif self._max_samples is not None and self._n_observed >= self._max_samples:
            decision = Decision.INCONCLUSIVE

        if decision is not Decision.CONTINUE:
            self._terminal = True

        return SPRTResult(
            value=sample,
            index=index,
            decision=decision,
            cumulative_llr=self._cumulative_llr,
            lower_bound=self._lower,
            upper_bound=self._upper,
            n_observed=self._n_observed,
        )

    def reset(self) -> None:
        self._cumulative_llr = 0.0
        self._n_observed = 0
        self._terminal = False


def sprt(
    *,
    llr: Callable[[S], float],
    alpha: float = 0.05,
    beta: float = 0.10,
    max_samples: int | None = None,
) -> SPRT[S]:
    return SPRT(llr=llr, alpha=alpha, beta=beta, max_samples=max_samples)
