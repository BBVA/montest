Testing Montest
===============

This page is for Montest maintainers and framework contributors. Application
tests should follow the domain-first workflow in :doc:`integrations` and usually
assert only a named domain decision. Start runnable application examples at
`examples/pytest/README.md <../examples/pytest/README.md>`_.

Test philosophy
---------------

Prefer deterministic oracle tests over probabilistic simulations. Hypothesis is
used to generate finite traces and composite shapes, not to assert empirical
false-positive or false-negative rates. Nominal alpha/beta targets and Wald
thresholds are not unconditional exact guarantees.

High-signal core invariants
---------------------------

SPRT tests should cover:

* cumulative log-likelihood traces;
* Wald boundary equality and H0/H1 sign convention;
* reset replay and terminal-state errors; and
* finite ``max_samples`` inconclusive behavior.

Composite tests should cover:

* mapping-order observation;
* ``AllOf`` waiting for all direct children;
* ``AnyOf`` short-circuiting only on ``ACCEPT_H1``;
* ``None`` entries for terminal or skipped children;
* direct-child ``n_decided`` and ``n_total`` counts;
* nested composite results preserved under direct keys; and
* reset replay.

pytest adapter protocol invariants
----------------------------------

Framework tests must cover the public replay and context protocol:

* every ``iter(cached_samples)`` cursor starts at sample zero independently;
* cursors replay cached sample objects by identity, and a longer consumer
  generates only the uncached suffix, so source calls equal the longest prefix,
  not the sum of cursor lengths;
* concurrent cursors requesting an uncached position generate it once and
  replay it to the other cursor;
* an ordinary source exception leaves the position retryable, while source
  ``StopIteration`` becomes the documented chained ``RuntimeError``;
* a stochastic run follows its ``NEW``, ``ACTIVE``, and ``EXITED`` lifecycle,
  permits exactly one outstanding raw sample, and requires it to be observed
  before another is requested;
* a criterion error leaves the wrapper's observation count and terminal result
  unchanged while leaving the raw sample pending; and
* terminal decision mismatch messages, lifecycle-error precedence, result
  availability after exit, and exception propagation remain stable.

Unlike feature tests, framework tests should inspect public ``SPRTResult`` and
``CompositeResult`` evidence when verifying the adapter/criterion contract.
They should verify direct-child ``terminal_results``, skipped/pending child
behavior, and ``n_decided``/``n_total`` where relevant. A composite's terminal
result does not imply every child decided, and shared child inputs are
correlated; do not turn composite evidence into an unsupported family-wise
error claim.

Avoid
-----

Do not add tests that:

* depend on unseeded randomness;
* assert statistical guarantees through small simulations;
* duplicate private implementation details as the oracle; or
* assert private attributes.
