Testing Montest
===============

Test philosophy
---------------

Prefer deterministic oracle tests over probabilistic simulations. Hypothesis is
used to generate finite traces and composite shapes, not to assert empirical
false-positive or false-negative rates.

High-signal invariants
----------------------

SPRT tests should cover:

* cumulative log-likelihood traces;
* Wald boundary equality;
* H0/H1 sign convention;
* reset replay;
* terminal-state errors;
* inconclusive ``max_samples`` behavior.

Composite tests should cover:

* mapping-order observation;
* ``AllOf`` waiting for all direct children;
* ``AnyOf`` short-circuiting only on ``ACCEPT_H1``;
* ``None`` entries for terminal or skipped children;
* direct-child ``n_decided`` and ``n_total`` counts;
* nested composite results being preserved under direct keys;
* reset replay.

Avoid
-----

Do not add tests that:

* depend on unseeded randomness;
* assert statistical guarantees through small simulations;
* duplicate private implementation details as the oracle;
* require optional testing-framework adapters that do not exist yet;
* assert private attributes.
