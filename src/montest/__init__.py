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

from montest._composite import AllOf, AnyOf, CompositeResult
from montest._criterion import StoppingCriterion
from montest._decision_monoid import (
    ALL_OF_DECISION_MONOID,
    ANY_OF_DECISION_MONOID,
    DecisionMonoid,
)
from montest._iterator_async import AsyncSequentialIterator
from montest._iterator_sync import SequentialIterator
from montest._types import Decision, ObservationResult
from montest.algorithms.sprt import SPRT, SPRTResult, sprt

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "AllOf",
    "ALL_OF_DECISION_MONOID",
    "AnyOf",
    "ANY_OF_DECISION_MONOID",
    "AsyncSequentialIterator",
    "CompositeResult",
    "Decision",
    "DecisionMonoid",
    "ObservationResult",
    "SPRT",
    "SPRTResult",
    "SequentialIterator",
    "StoppingCriterion",
    "sprt",
]
