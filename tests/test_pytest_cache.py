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

import threading

import pytest

from montest.pytest import CachedSamples, cached_samples


def test_independent_interleaved_cursors_replay_identical_cached_objects() -> None:
    generated: list[object] = []

    def generate() -> object:
        value = object()
        generated.append(value)
        return value

    samples = CachedSamples(generate)
    first_cursor = iter(samples)
    second_cursor = iter(samples)

    first_zero = next(first_cursor)
    second_zero = next(second_cursor)
    second_one = next(second_cursor)
    first_one = next(first_cursor)

    assert first_zero is generated[0]
    assert second_zero is first_zero
    assert second_one is generated[1]
    assert first_one is second_one
    assert len(generated) == 2


def test_longer_consumer_extends_only_uncached_suffix() -> None:
    generated: list[object] = []

    def generate() -> object:
        value = object()
        generated.append(value)
        return value

    samples = cached_samples(generate)
    shorter = iter(samples)
    longer = iter(samples)

    shared_prefix = [next(shorter) for _ in range(3)]
    assert len(generated) == 3

    replayed_prefix = [next(longer) for _ in range(3)]
    for replayed, original in zip(replayed_prefix, shared_prefix, strict=True):
        assert replayed is original
    assert len(generated) == 3

    suffix = [next(longer) for _ in range(2)]

    assert suffix == generated[3:]
    assert suffix[0] is generated[3]
    assert suffix[1] is generated[4]
    assert len(generated) == 5


def test_synchronized_cursors_generate_uncached_index_once() -> None:
    generated = object()
    source_calls = 0
    source_calls_lock = threading.Lock()
    start = threading.Barrier(3)
    results: list[object | None] = [None, None]
    errors: list[BaseException | None] = [None, None]

    def _record_generated_value() -> object:
        nonlocal source_calls
        with source_calls_lock:
            source_calls += 1
        return generated

    samples = cached_samples(_record_generated_value)

    def consume(slot: int) -> None:
        try:
            start.wait()
            results[slot] = next(iter(samples))
        except BaseException as error:
            errors[slot] = error

    threads = [threading.Thread(target=consume, args=(slot,)) for slot in range(2)]
    for thread in threads:
        thread.start()

    start.wait()
    for thread in threads:
        thread.join()

    assert errors == [None, None]
    assert source_calls == 1
    assert results[0] is generated
    assert results[1] is generated


def test_ordinary_generation_errors_leave_cursor_at_same_cache_index() -> None:
    first_error = LookupError("first attempt failed")
    second_error = OSError("second attempt failed")
    first_value = object()
    second_value = object()
    outcomes: list[BaseException | object] = [
        first_error,
        first_value,
        second_error,
        second_value,
    ]
    source_calls = 0

    def generate() -> object:
        nonlocal source_calls
        source_calls += 1
        outcome = outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    samples = cached_samples(generate)
    first_cursor = iter(samples)
    second_cursor = iter(samples)

    with pytest.raises(LookupError) as first_caught:
        next(first_cursor)
    assert first_caught.value is first_error

    assert next(second_cursor) is first_value
    assert next(first_cursor) is first_value

    with pytest.raises(OSError) as second_caught:
        next(first_cursor)
    assert second_caught.value is second_error

    assert next(first_cursor) is second_value
    assert next(second_cursor) is second_value
    assert source_calls == 4


def test_generator_stop_iteration_becomes_chained_runtime_error_and_allows_retry() -> (
    None
):
    stop = StopIteration("source is exhausted")
    value = object()
    outcomes: list[StopIteration | object] = [stop, value]
    source_calls = 0

    def generate() -> object:
        nonlocal source_calls
        source_calls += 1
        outcome = outcomes.pop(0)
        if isinstance(outcome, StopIteration):
            raise outcome
        return outcome

    samples = CachedSamples(generate)
    cursor = iter(samples)

    with pytest.raises(RuntimeError) as caught:
        next(cursor)

    assert str(caught.value) == "Sample generator raised StopIteration."
    assert caught.value.__cause__ is stop
    assert source_calls == 1

    assert next(cursor) is value
    assert next(iter(samples)) is value
    assert source_calls == 2
