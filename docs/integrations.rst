pytest integration
==================

Montest helps when one call cannot answer a product question reliably. Instead
of treating a single random result as a pass or failure, a test collects
repeated outcomes until it has enough evidence for a decision, or reaches the
budget chosen for that test. This is useful for randomized algorithms, sampled
services, simulations, probabilistic models, and live systems with controlled
nondeterminism.

Run the examples first
----------------------

The executable pytest examples are the primary learning path. From a repository
checkout, run the offline scenarios:

.. code-block:: console

   uv run --project examples/pytest \
      python examples/pytest/runner.py run offline -q

This runs the coin, dice, and roulette scenarios without credentials, network
access, or paid API calls. Read the examples in this order:

* `coin fairness
  <https://github.com/BBVA/montest/blob/main/examples/pytest/tests/test_coin_fairness.py>`_
  starts with one Boolean observation per flip and a named domain requirement;
* `dice fairness
  <https://github.com/BBVA/montest/blob/main/examples/pytest/tests/test_dice_fairness.py>`_
  maps one raw pair of rolls to two related child observations;
* `roulette fairness
  <https://github.com/BBVA/montest/blob/main/examples/pytest/tests/test_roulette_fairness.py>`_
  shows a three-child composite with a domain-specific resolver; and
* `LLM emoji behavior
  <https://github.com/BBVA/montest/blob/main/examples/pytest/tests/test_llm_emoji.py>`_
  applies the same workflow to live text responses and a fixed model
  configuration.

The `complete example guide
<https://github.com/BBVA/montest/tree/main/examples/pytest>`_ explains setup,
runner groups, known-defect demonstrations, and the paid live scenario.


Installation
------------

Install the optional adapter in the environment that runs a consuming project's
pytest tests:

.. code-block:: console

   pip install "montest[pytest] @ git+https://github.com/BBVA/montest.git@main"

This command installs Montest from Git. The ``uv`` command above instead runs
the examples from a repository checkout.

Import the adapter explicitly:

.. code-block:: python

   from montest.pytest import CachedSamples, cached_samples, stochastic

The base ``montest`` package remains dependency-free: ``import montest`` does
not import pytest. Montest supplies no pytest plugin, marker, decorator, or
injected fixture. Ordinary pytest fixtures define the data source and control
its lifetime. See :doc:`installation` for the package boundary.

The pytest workflow
-------------------

Every executable example follows the same public sequence:

#. An ordinary pytest fixture returns a ``CachedSamples`` instance whose scope
   controls the lifetime of its process-local cache.
#. The test constructs a fresh stopping criterion from its acceptable and
   concerning domain models.
#. ``stochastic(...)`` yields one raw sample at a time. The test converts that
   sample to one domain observation and submits it with ``run.observe(...)``.
#. When the criterion stops iteration, ``run.assert_decision(...)`` checks one
   named domain outcome.

A complete expected-behavior test
---------------------------------

The coin example keeps statistical plumbing outside the test body. The test
therefore exposes only the fixture, raw sample, observation, criterion, and
required decision:

.. literalinclude:: ../examples/pytest/tests/test_coin_fairness.py
   :language: python
   :pyobject: test_fair_coin_has_no_selected_side_bias_for_heads
   :caption: Expected behavior from the executable coin example

The `complete coin module
<https://github.com/BBVA/montest/blob/main/examples/pytest/tests/test_coin_fairness.py>`_
defines the requirement constants, source configuration, likelihood-ratio
helper, cache fixtures, expected-behavior tests, and known-defect demonstration.

How to read the test
--------------------

``fixture``
   An ordinary pytest fixture owns one source configuration and returns cached
   raw samples. Its scope controls how long that cache lives.

``raw sample``
   One value produced by the system or simulator: a flip, dice pair, wheel
   spin, API response, or generated text.

``observation``
   The domain fact extracted from one raw sample and submitted to the
   criterion, such as ``is_heads`` or ``contains_emoji(response)``. It need not
   have the same type as the raw sample.

``criterion``
   A fresh stopping rule for one test. It accumulates observations and decides
   when there is enough evidence. Construct it from the requirement, not from
   another test's state.

``run``
   The explicit context-managed bridge between raw samples and the criterion.
   It yields one raw sample; the test must submit exactly one derived
   observation before requesting the next sample.

``decision``
   The terminal conclusion. A feature test normally asserts a named domain
   outcome rather than a numeric evidence trace.

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

Cached samples and distribution boundaries
------------------------------------------

``cached_samples(generate)`` stores successful raw values in memory. Every
``iter(samples)`` cursor starts at sample zero, replays the shared cached prefix,
and extends only the uncached suffix. Cached objects are returned without
copying and must be treated as immutable.

Fixture scope controls cache scope. A session-scoped fixture shares one cache
inside one pytest process. Use a separate fixture and cache whenever a setting
changes the data-generating distribution: model or model version, prompt, input
population, temperature, tool configuration, simulator parameters, or any
other source configuration. pytest-xdist workers are separate processes and
therefore create separate caches and can repeat external calls.

Independent cursors provide execution-state independence, not statistical
independence. Tests replaying shared raw observations are correlated. Montest
does not apply multiple-testing or family-wise-error corrections, including
when several child criteria receive facts derived from one raw sample.

For each test, derived observations must satisfy the criterion's modeled
likelihood-ratio process, usually correctly specified within-test iid
observations or another explicitly valid conditional model. Fix the source
configuration, raw-to-observation mapping, criterion, and cache reuse before
seeing results; do not adapt them to another test's outcome. A finite
``max_samples`` may produce ``Decision.INCONCLUSIVE``.

Practical error handling
------------------------

Let source, conversion, and criterion exceptions fail normally. Do not relabel
an unavailable credential, network failure, invalid source configuration, or
criterion bug as an H1 decision or as the known-defect xfail. The context
preserves the original exception.

For routine feature tests, assert only the named domain decision. ``run.result``
and ``SPRTResult`` fields are diagnostic tools for investigating a surprising
result, not normal product assertions. For composites, ``CompositeResult`` can
show terminal direct-child results, but an early composite decision may leave
other children pending or skipped; absent child evidence is not evidence for
that child.

The `live LLM example
<https://github.com/BBVA/montest/blob/main/examples/pytest/tests/test_llm_emoji.py>`_
keeps missing-credential handling separate from its strict known-defect xfail.
Without credentials it makes no paid request; that skip condition is not a
substitute for running the credentialed test.

Protocol constraints
--------------------

A run is single-use and active only inside its context. Each yielded raw sample
must receive exactly one observation before the next sample is requested.
Construct a fresh criterion for every test; the adapter does not reset it.

Source, conversion, and criterion exceptions propagate unchanged. A clean
context exit requires the last yielded sample to have been observed and the
criterion to have reached a terminal decision. After exit, the terminal result,
observation count, and ``assert_decision`` remain available.

The adapter is synchronous only. It provides no asynchronous source API,
asynchronous context manager, pytest plugin, or injected fixture. Behave support
is planned rather than implemented. Exact methods, lifecycle exceptions, result
fields, and assertion diagnostics are documented in :doc:`api`.
