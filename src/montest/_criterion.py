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

from typing import Any, Protocol, TypeVar, runtime_checkable

from montest._types import ObservationResult

S_contra = TypeVar("S_contra", contravariant=True)
R_co = TypeVar("R_co", covariant=True, bound=ObservationResult[Any])


@runtime_checkable
class StoppingCriterion(Protocol[S_contra, R_co]):
    def observe(self, sample: S_contra, *, index: int) -> R_co: ...

    def reset(self) -> None: ...
