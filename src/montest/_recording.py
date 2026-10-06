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

"""Private, append-only record of one stochastic run."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, TextIO, TypeAlias
from uuid import uuid4

from montest._composite import CompositeResult
from montest._types import ObservationResult
from montest.algorithms.sprt._result import SPRTResult

JSONValue: TypeAlias = (
    "None | bool | int | float | str | list[JSONValue] | dict[str, JSONValue]"
)


def _validate(value: object) -> None:
    if value is None or isinstance(value, (bool, int, float, str)):
        return
    if isinstance(value, list):
        for item in value:
            _validate(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("Recording object keys must be strings.")
            _validate(item)
        return
    raise TypeError(f"Recording does not support {type(value).__name__} values.")


def validate_value(value: JSONValue) -> None:
    _validate(value)
    json.dumps(value, allow_nan=False)


def _line(event: dict[str, JSONValue]) -> str:
    _validate(event)
    return json.dumps(event, allow_nan=False, separators=(",", ":")) + "\n"


def _children(
    results: Mapping[str, ObservationResult[Any] | None],
) -> dict[str, JSONValue]:
    return {
        key: None if child is None else serialize_result(child)
        for key, child in results.items()
    }


def serialize_result(result: ObservationResult[Any]) -> dict[str, JSONValue]:
    """Preserve evidence without serializing the criterion input twice."""
    data: dict[str, JSONValue] = {
        "kind": "observation",
        "index": result.index,
        "decision": result.decision.value,
    }
    if isinstance(result, SPRTResult):
        data.update(
            kind="sprt",
            cumulative_llr=result.cumulative_llr,
            lower_bound=result.lower_bound,
            upper_bound=result.upper_bound,
            n_observed=result.n_observed,
        )
    elif isinstance(result, CompositeResult):
        data.update(
            kind="composite",
            results=_children(result.results),
            terminal_results=_children(result.terminal_results),
            n_decided=result.n_decided,
            n_total=result.n_total,
        )
    return data


class RunWriter:
    def __init__(self, path: Path, metadata: Mapping[str, JSONValue]) -> None:
        start: dict[str, JSONValue] = {
            "type": "run_start",
            "schema_version": 1,
            "run_id": uuid4().hex,
            "metadata": dict(metadata),
        }
        line = _line(start)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._file: TextIO = path.open("x", encoding="utf-8")
        try:
            self._file.write(line)
            self._file.flush()
        except BaseException:
            try:
                self._file.close()
            except BaseException:
                pass
            raise

    def write(self, event: dict[str, JSONValue]) -> None:
        line = _line(event)
        self._file.write(line)
        self._file.flush()

    def close(self) -> None:
        self._file.close()


def error_type(error: BaseException) -> str:
    cls = type(error)
    return f"{cls.__module__}.{cls.__qualname__}"
