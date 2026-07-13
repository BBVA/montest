pytest integration
==================

Montest helps when one call cannot answer a product question reliably. Instead
of treating a single random result as a pass or failure, a test collects
repeated outcomes until it has enough evidence for a decision, or reaches the
budget chosen for that test. This is useful for randomized algorithms, sampled
services, simulations, probabilistic models, and live systems with controlled
nondeterminism.

Start with the complete, runnable learning path in
`examples/pytest/README.md <../examples/pytest/README.md>`_. It explains the
same workflow in progressively richer tests:

* `coin fairness <../examples/pytest/tests/test_coin_fairness.py>`_ starts with
  one Boolean observation per flip and a named domain requirement;
* `dice fairness <../examples/pytest/tests/test_dice_fairness.py>`_ shows how
  one raw roll can become several related observations;
* `roulette fairness <../examples/pytest/tests/test_roulette_fairness.py>`_
  shows a composed requirement; and
* `LLM emoji behavior <../examples/pytest/tests/test_llm_emoji.py>`_ applies
  the pattern to live text responses and a fixed model configuration.

Installation
------------

Install the optional adapter in the environment that runs pytest:

.. code-block:: console

   pip install "montest[pytest]"

Import it explicitly:

.. code-block:: python

   from montest.pytest import CachedSamples, cached_samples, stochastic

The base ``montest`` package remains dependency-free: ``import montest`` does
not import pytest. Montest supplies no pytest plugin, marker, decorator, or
injected fixture. Your ordinary pytest fixtures define the data source and
control its lifetime. See :doc:`installation` for the package boundary.

The developer mental model
--------------------------

Read a stochastic test in this order:

``fixture``
   An ordinary pytest fixture owns a source configuration and returns cached
   raw samples. Its scope controls how long the cache lives.

``raw sample``
   One value produced by the system or simulator: a flip, dice pair, wheel
   spin, API response, or generated text.

``observation``
   The domain fact extracted from one raw sample and submitted to the
   criterion: for example, ``is_heads`` or ``contains_emoji(response)``. It is
   not necessarily the raw value.

``criterion``
   A fresh stopping rule for this one test. It accumulates observations and
   decides when there is enough evidence. Create it from the requirement, not
   from a previous test's state.

``run``
   The explicit context-managed bridge between raw samples and the criterion.
   It yields one raw sample; the test must submit exactly one derived
   observation before requesting the next sample.

``decision``
   The terminal conclusion. A test normally asserts the named domain outcome,
   not a numeric evidence trace.

A canonical test
----------------

Put statistical plumbing in a small domain-named helper. Keep the test body
about the behavior being required:

.. code-block:: python

   import random
   import math


   import pytest

   from montest import Decision, sprt
   from montest.pytest import CachedSamples, cached_samples, stochastic

   NO_SELECTED_SIDE_BIAS_DETECTED = Decision.ACCEPT_H0

   @pytest.fixture(scope="session")
   def fair_flips() -> CachedSamples[bool]:
       rng = random.Random(42)
       return cached_samples(lambda: rng.random() < 0.5)

   def selected_side_evidence(is_heads: bool) -> float:
       return (
           math.log(0.65 / 0.50)
           if is_heads
           else math.log(0.35 / 0.50)
       )

   def detect_selected_side_bias():
       # Keep the likelihood model and its named parameters beside this helper.
       return sprt(llr=selected_side_evidence, alpha=0.05, beta=0.10,
                   max_samples=500)

   def test_coin_has_no_selected_side_bias(
       fair_flips: CachedSamples[bool],
   ) -> None:
       with stochastic(fair_flips, detect_selected_side_bias()) as run:
           for is_heads in run:
               run.observe(is_heads)

       run.assert_decision(NO_SELECTED_SIDE_BIAS_DETECTED)

The fixture provides raw flips. ``is_heads`` is the observation. The helper
encodes the requirement's model. The final assertion uses a domain name, so a
reader need not understand the criterion implementation to understand what the
test requires.

Requirement first; statistical terms second
--------------------------------------------

Choose an *acceptable* behavior and a *concerning* departure before choosing a
stopping rule. For a coin, “about 50% heads is acceptable” and “65% heads is
concerning” are domain statements. A finite budget, such as 500 flips, is also
a domain decision about cost and latency.

For an SPRT, Montest calls the acceptable baseline ``H0`` and the concerning
alternative ``H1``. Therefore, when the requirement is normal behavior:

* ``Decision.ACCEPT_H0`` supports the configured acceptable model over the
  chosen concerning alternative;
* ``Decision.ACCEPT_H1`` reports the concerning behavior and normally fails
  that requirement; and
* ``Decision.INCONCLUSIVE`` says the budget ended before either conclusion had
  enough evidence. It is neither a pass nor evidence that the behavior is
  acceptable.

An H0 result does not prove universal correctness, estimate every possible
rate, or prove an absolute policy. It is evidence about the explicitly
configured models and inputs. Define in advance what an inconclusive result
means operationally: collect more data, investigate, retry under a new test
run, or block the relevant change.

The examples name ``SPRT_ALPHA`` and ``SPRT_BETA`` because they are deliberate
risk/cost choices. They are nominal Type-I and Type-II targets used to construct
approximate Wald thresholds, not observed error frequencies or exact promises.
Lower ``SPRT_ALPHA`` asks for stronger evidence before flagging H1: fewer
nominal false alerts, usually more samples and more risk of reaching the finite
budget. Lower ``SPRT_BETA`` asks for stronger evidence before accepting H0:
fewer nominal misses, usually more samples and more inconclusive outcomes.
Boundary overshoot and model assumptions mean these are not unconditional exact
alpha/beta guarantees. See :doc:`sprt` for the mathematical contract.

Expected behavior and known defects
------------------------------------

A normal feature test uses a requirement-aligned source and one final assertion
for the acceptable domain decision. Do not invent a broken variant merely to
use Montest.

The learning examples also contain explicit known-defect demonstrations. They
keep the *same* acceptable requirement and final assertion, but deliberately
supply a bad source or configuration; its H1 decision makes that assertion fail.
They use ``pytest.mark.xfail(strict=True, raises=pytest.fail.Exception)``:

* ``strict=True`` makes an unexpected pass (XPASS) fail, so a repaired defect
  cannot silently remain marked as known; and
* ``raises=pytest.fail.Exception`` limits the xfail to the expected final
  pytest assertion failure. Generation, credential, network, API, and
  programming errors remain ordinary failures.

This is pytest behavior, not a special Montest outcome. H1 is never the
expected successful result of a test that requires H0.

Caching and distributions
-------------------------

``cached_samples(generate)`` stores successful raw values in memory. Each
``iter(samples)`` cursor begins at sample zero, so tests using the same fixture
replay the same prefix. A test that needs more values extends only the uncached
suffix. This is useful for expensive, seeded, or externally obtained samples;
it does not copy cached objects, so treat them as immutable.

Fixture scope chooses cache scope. A session-scoped fixture shares one cache in
one pytest process. Use a separate fixture instance whenever a setting changes
the data-generating distribution: model or model version, prompt, input
population, temperature, tool configuration, simulator parameters, or any
other source configuration. xdist workers are separate processes and therefore
make separate external calls.

Shared samples and statistical independence
-------------------------------------------

Every test gets an independent cursor beginning at cached sample zero, and
differently sized sequential tests replay the same prefix before extending the
shared cache. Cursor independence is execution-state independence only.

Replaying a shared cache does not change one test's marginal input prefix
relative to consuming the same process-local stream afresh. It preserves only
the same nominal/approximate operating characteristics the configured criterion
would have had on that stream; it does not create exact alpha/beta guarantees.
For each test, derived observations must satisfy the criterion's modeled
likelihood-ratio process—usually correctly specified within-test iid
observations or another explicitly valid conditional model. Keep generation
configuration unchanged. Fix the raw-to-observation mapping, criterion, and
cache reuse before seeing results; do not adapt them to another test's outcome.
A finite ``max_samples`` may produce ``Decision.INCONCLUSIVE``.

Tests sharing raw observations are correlated, not statistically independent.
Montest does not apply multiple-testing or family-wise error corrections. This
is especially important when several child criteria use one raw sample: a
composite decision has different, uncorrected operating characteristics from
any individual child.

Use separate fixture instances for different models, model versions, prompts,
input distributions, temperatures, tool configurations, or any other setting
that changes the data-generating distribution. Treat cached objects as
immutable. In-memory session caches are per pytest process, so xdist workers
make separate external calls.

Practical error handling
------------------------

Let source and domain exceptions fail normally. Do not relabel an unavailable
credential, network failure, invalid source configuration, or criterion bug as
an H1 decision or an expected xfail. The context preserves an exception raised
by its body, source, or criterion so its original cause remains visible.

For routine feature tests, assert only the domain decision. ``run.result`` and
``SPRTResult`` fields are diagnostic tools for investigating a surprising test
result, not normal product assertions. For composites, ``CompositeResult`` can
show terminal direct-child results, but an early composite decision may leave
other children pending or skipped; absent child evidence is not evidence for
that child. Do not reconstruct child evidence from the last raw sample.

If a child criterion in a composite raises, that exception is not converted to a
child decision and later children for that observation are not processed. Earlier
children may already have received the observation or reached a terminal state;
the composite and run cannot roll those child mutations back. Fix the child
criterion or input model and rerun with a fresh criterion rather than treating
that partial state as a composite conclusion.

Advanced adapter reference
--------------------------

The adapter is synchronous only. It intentionally has no asynchronous context
manager or async source API, and Behave support is planned rather than
implemented. It delegates statistical transitions to the supplied criterion and
does not reset it; construct a fresh criterion for each test.

``CachedSamples`` has an append-only, process-local cache. Its cursors return
the original object identity. One lock protects lookup, generation, and append,
so concurrent cursors do not generate the same uncached index twice. An ordinary
source exception is propagated unchanged without advancing or caching; a later
attempt retries that index. A source ``StopIteration`` becomes
``RuntimeError("Sample generator raised StopIteration.")`` with the original
exception as its cause, likewise without advancing or caching.

A ``StochasticRun`` is one-use: entering it opens one cursor; re-entering raises
``RuntimeError("Stochastic run cannot be entered more than once.")``. Before
entry and after exit, iteration, ``next(run)``, and ``observe`` raise
``RuntimeError("Stochastic run is not active.")``. While active, a terminal run
stops iteration; otherwise a second raw sample before observing the first raises
``RuntimeError("Current sample must be observed before requesting another sample.")``.
``observe`` after a terminal decision raises
``RuntimeError("Stochastic run already reached a terminal decision.")``; without
a pending sample it raises ``RuntimeError("No sample is awaiting an observation.")``.

A successful observation is passed to the criterion at its zero-based index,
then increments ``n_observed`` exactly once. If the criterion raises, its
exception and any internal mutation are preserved, but the run's count/result
stay unchanged and its raw sample remains pending. A clean context exit with a
pending sample raises ``RuntimeError("Stochastic run exited with an unobserved sample.")``;
a clean non-terminal exit instead raises
``RuntimeError("Stochastic run exited before the criterion reached a terminal decision.")``.
After exit, only ``n_observed``, an already-terminal ``result``, and
``assert_decision`` remain usable. Accessing a non-terminal result raises
``RuntimeError("Stochastic run has not reached a terminal decision.")``.
``assert_decision(Decision.CONTINUE)`` raises
``ValueError("expected decision must be terminal")``.

When the context body, source, or criterion raises, ``__exit__`` makes the run
inactive and returns ``False`` without replacing that exception with lifecycle
validation. On a clean exit, the unobserved-sample error takes precedence over
the non-terminal error. A terminal mismatch calls ``pytest.fail(...,
pytrace=False)`` with exactly::

   Montest stochastic decision mismatch
   expected: {expected.value}
   actual: {result.decision.value}
   observations: {n_observed}
   result: {result!r}

The full public symbols are listed in :doc:`api`.
