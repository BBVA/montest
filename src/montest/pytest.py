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

"""Use Montest from ordinary synchronous pytest tests.

Write a fixture that supplies raw samples, such as API responses, dice rolls, or
model output. Wrap its expensive sample callable with :func:`cached_samples` to
replay the samples that previous tests have already requested. Each test creates
a fresh stopping criterion, then drives it explicitly::

    with stochastic(samples, criterion) as run:
        for raw_sample in run:
            observation = convert_to_domain_observation(raw_sample)
            run.observe(observation)
        run.assert_decision(expected_decision)

The context yields raw values so the test owns the domain conversion; pass
exactly one resulting observation to :meth:`StochasticRun.observe` for each
yielded value. The fresh criterion determines when sufficient evidence exists,
and :meth:`StochasticRun.assert_decision` checks the requirement: acceptable
behavior usually expects ``Decision.H0`` and concerning behavior usually expects
``Decision.H1``. ``Decision.INCONCLUSIVE`` is also a terminal requirement when a
finite run cannot decide.

This module is a synchronous adapter, not a pytest plugin. It registers no
plugin and injects no fixture; fixture scope and sample lifetime remain under
the test suite's control. See examples/pytest for complete coin, dice,
roulette, and LLM tutorials.
"""
from __future__ import annotations

import enum
import threading
from collections.abc import Callable, Iterable, Iterator
from types import TracebackType
from typing import Any, Generic, Literal, Self, TypeVar

import pytest

from montest._criterion import StoppingCriterion
from montest._types import Decision, ObservationResult

Raw = TypeVar("Raw")
Observed = TypeVar("Observed")
ResultT = TypeVar("ResultT", bound=ObservationResult[Any])

__all__ = ["CachedSamples", "StochasticRun", "cached_samples", "stochastic"]


class _CachedSamplesCursor(Generic[Raw], Iterator[Raw]):
    def __init__(self, source: CachedSamples[Raw]) -> None:
        self._source = source
        self._index = 0

    def __iter__(self) -> _CachedSamplesCursor[Raw]:
        return self

    def __next__(self) -> Raw:
        with self._source._lock:
            if self._index < len(self._source._samples):
                sample = self._source._samples[self._index]
            else:
                try:
                    sample = self._source._generate()
                except StopIteration as error:
                    raise RuntimeError(
                        "Sample generator raised StopIteration."
                    ) from error
                self._source._samples.append(sample)

            self._index += 1
            return sample


class CachedSamples(Generic[Raw], Iterable[Raw]):
    """Replay one process-local raw-sample stream through independent cursors.

    Create one instance in a pytest fixture, commonly a session-scoped fixture
    when several tests should reuse expensive calls. Every ``iter(samples)``
    cursor starts at sample zero. It replays the cached prefix first and extends
    the shared cache only when it reaches a new position, so a longer consumer
    generates only the suffix that no cursor has requested.

    Cached objects are returned without copying. Treat every raw object as
    immutable: mutating it changes what later cursors replay. The cache lives
    only in this fixture instance and pytest process; xdist workers have
    separate caches and can make separate external calls.

    If the source callable raises an exception, that same exception is
    propagated, nothing is cached, and the cursor remains at that position for
    a later retry. A source ``StopIteration`` is converted to ``RuntimeError``
    because sources must return samples rather than signal iterator exhaustion.
    """

    def __init__(self, generate: Callable[[], Raw]) -> None:
        """Initialize a source whose returned raw values will be cached.

        :param generate: Zero-argument callable that produces one raw sample.
            The callable is invoked at most once per uncached position in this
            process.
        """
        self._generate = generate
        self._samples: list[Raw] = []
        self._lock = threading.Lock()

    def __iter__(self) -> Iterator[Raw]:
        """Return a new cursor starting at the first cached sample.

        The cursor is independent of other cursors' positions but shares their
        cache. It returns cached object identities unchanged.
        """
        return _CachedSamplesCursor(self)


def cached_samples(generate: Callable[[], Raw]) -> CachedSamples[Raw]:
    """Create a replayable raw-sample source for a pytest fixture.

    This is the concise fixture-facing constructor for :class:`CachedSamples`.
    Keep the returned object in the fixture scope that should share calls:
    session scope replays one process-local prefix across tests, while a
    function-scoped fixture gives each test a separate cache. See
    :class:`CachedSamples` for cursor, immutability, xdist, and exception
    behavior.

    :param generate: Zero-argument callable that supplies each uncached raw
        sample.
    :returns: A source with a fresh shared in-memory cache.
    """

    return CachedSamples(generate)


class _RunState(enum.Enum):
    NEW = enum.auto()
    ACTIVE = enum.auto()
    EXITED = enum.auto()


class StochasticRun(Generic[Raw, Observed, ResultT], Iterator[Raw]):
    """Explicitly turn cached raw samples into criterion observations.

    Use one run for one test and one fresh criterion. Entering the context opens
    a dedicated cursor over ``samples``. Iteration yields a raw value; transform
    it in the test body and call :meth:`observe` exactly once before requesting
    the next raw value. This separation makes transformations such as
    ``response.status_code == 200`` or ``roll >= 4`` visible in the test.

    The supplied criterion owns the evidence calculation and stops the iterator
    after a terminal decision. A run is single-use: it is active only inside its
    context, cannot be re-entered, and its raw iteration and ``observe`` calls
    fail outside that context. On a clean exit, every yielded raw sample must
    have been observed and the criterion must have reached a terminal decision.

    After completion, inspect :attr:`result` for the terminal result record and
    use :meth:`assert_decision` to express the domain requirement. The count in
    :attr:`n_observed` remains available at every lifecycle stage. See
    examples/pytest for complete coin, dice, roulette, and LLM tutorials.
    """

    def __init__(
        self,
        samples: CachedSamples[Raw],
        criterion: StoppingCriterion[Observed, ResultT],
    ) -> None:
        """Bind a replayable raw source to a fresh stopping criterion.

        :param samples: Cached raw values to yield to the test body.
        :param criterion: Fresh criterion that receives the test's derived
            observations. It is not reset automatically.
        """
        self._samples = samples
        self._criterion = criterion
        self._state = _RunState.NEW
        self._cursor: Iterator[Raw] | None = None
        self._outstanding = False
        self._n_observed = 0
        self._result: ResultT | None = None

    def __enter__(self) -> Self:
        """Enter the one-use run and open its independent sample cursor.

        :returns: This active run, ready to yield raw samples.
        :raises RuntimeError: If this run was already entered or exited.
        """
        if self._state is not _RunState.NEW:
            raise RuntimeError("Stochastic run cannot be entered more than once.")
        self._state = _RunState.ACTIVE
        self._cursor = iter(self._samples)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        """Close the run and validate a clean context-body completion.

        Exceptions from the context body are never replaced. Without such an
        exception, exit requires that the last yielded raw sample was observed
        and that the criterion produced a terminal result.
        """
        self._state = _RunState.EXITED
        if exc_type is not None:
            return False
        if self._outstanding:
            raise RuntimeError("Stochastic run exited with an unobserved sample.")
        if self._result is None:
            raise RuntimeError(
                "Stochastic run exited before the criterion reached "
                "a terminal decision."
            )
        return False

    def __iter__(self) -> Self:
        """Return this active run as its raw-sample iterator.

        :raises RuntimeError: If called before entry or after context exit.
        """
        self._ensure_active()
        return self

    def __next__(self) -> Raw:
        """Yield the next raw sample for domain-specific conversion.

        Call :meth:`observe` once with the derived observation before calling
        ``next`` again. Iteration ends when the criterion has a terminal
        decision.

        :raises RuntimeError: If inactive or if the current raw sample has not
            yet been observed.
        :raises StopIteration: If the criterion already reached a terminal
            decision.
        """
        self._ensure_active()
        if self._result is not None:
            raise StopIteration
        if self._outstanding:
            raise RuntimeError(
                "Current sample must be observed before requesting another sample."
            )

        assert self._cursor is not None
        sample = next(self._cursor)
        self._outstanding = True
        return sample

    def observe(self, observation: Observed) -> ResultT:
        """Submit the one derived observation for the current raw sample.

        The observation is not the raw value unless the raw domain is already
        the criterion's domain. For example, yield an HTTP response and submit
        a boolean success indicator. A successful submission is indexed in
        yield order and returns the criterion's result record.

        :raises RuntimeError: If inactive, no raw sample is awaiting an
            observation, or the criterion already made a terminal decision.
        """
        self._ensure_active()
        if self._result is not None:
            raise RuntimeError(
                "Stochastic run already reached a terminal decision."
            )
        if not self._outstanding:
            raise RuntimeError("No sample is awaiting an observation.")

        result = self._criterion.observe(observation, index=self._n_observed)
        self._outstanding = False
        self._n_observed += 1
        if result.decision is not Decision.CONTINUE:
            self._result = result
        return result

    @property
    def result(self) -> ResultT:
        """Return the criterion's terminal result record.

        The record remains readable after context exit. Composite criteria can
        expose their terminal child evidence through their result record.

        :raises RuntimeError: If no terminal decision has been reached.
        """
        if self._result is None:
            raise RuntimeError(
                "Stochastic run has not reached a terminal decision."
            )
        return self._result

    @property
    def n_observed(self) -> int:
        """Return how many derived observations were submitted successfully.

        This count is readable before entry, while active, and after exit.
        """
        return self._n_observed

    def assert_decision(self, expected: Decision) -> None:
        """Assert that the completed run reached a required terminal decision.

        Use ``Decision.H0`` for behavior the test considers acceptable,
        ``Decision.H1`` for behavior it considers concerning, or
        ``Decision.INCONCLUSIVE`` when that is the requirement. A mismatch
        fails the pytest test with the expected and actual decisions, count,
        and result record. ``Decision.CONTINUE`` is not a valid expectation.

        :param expected: Required terminal decision for this test.

        :raises RuntimeError: If the run has no terminal result.
        :raises ValueError: If ``expected`` is ``Decision.CONTINUE``.
        """
        if expected is Decision.CONTINUE:
            raise ValueError("expected decision must be terminal")

        result = self.result
        if result.decision is expected:
            return

        pytest.fail(
            "Montest stochastic decision mismatch\n"
            f"expected: {expected.value}\n"
            f"actual: {result.decision.value}\n"
            f"observations: {self._n_observed}\n"
            f"result: {result!r}",
            pytrace=False,
        )

    def _ensure_active(self) -> None:
        if self._state is not _RunState.ACTIVE:
            raise RuntimeError("Stochastic run is not active.")


def stochastic(
    samples: CachedSamples[Raw],
    criterion: StoppingCriterion[Observed, ResultT],
) -> StochasticRun[Raw, Observed, ResultT]:
    """Create an explicit context-managed run for one pytest test.

    This factory is equivalent to :class:`StochasticRun` construction. The
    canonical use is ``with stochastic(samples, criterion) as run:`` followed
    by a raw-to-observation conversion and one :meth:`StochasticRun.observe`
    call per yielded value, then :meth:`StochasticRun.assert_decision`. See
    examples/pytest for complete coin, dice, roulette, and LLM tutorials.

    :param samples: Replayable raw source, normally supplied by a pytest
        fixture.
    :param criterion: Fresh criterion for this test's derived observations.
    :returns: A new, inactive single-use run.
    """

    return StochasticRun(samples, criterion)
