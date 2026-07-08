Composition
===========

Montest composes criteria explicitly with ``AllOf`` and ``AnyOf``. Composite
keys are owned by the mapping passed to the composite, not by child criteria.

Decision monoids
----------------

Composite terminal decisions are resolved with explicit decision monoids.

``ANY_OF_DECISION_MONOID`` models disjunction over terminal decisions:

.. code-block:: python

   ACCEPT_H0 < INCONCLUSIVE < ACCEPT_H1

Its identity is ``ACCEPT_H0``. ``ACCEPT_H1`` is absorbing.

``ALL_OF_DECISION_MONOID`` models conjunction over terminal decisions:

.. code-block:: python

   ACCEPT_H1 < INCONCLUSIVE < ACCEPT_H0

Its identity is ``ACCEPT_H1``. ``ACCEPT_H0`` is absorbing.

Both monoids provide ``combine(left, right)`` and ``resolve(decisions)``.

Composite results
-----------------

``CompositeResult.results`` contains results from the current observation step.
A ``None`` entry means that the child was not observed on that step.

``CompositeResult.terminal_results`` contains the terminal result for every
direct child that has reached a terminal decision so far. Use this mapping to
inspect child-level evidence after a composite resolves.

``n_decided`` is always ``len(terminal_results)``. It counts direct children
with known terminal results; it does not mean the same thing as the composite
itself being terminal.

If ``results[key]`` is ``None`` and ``key`` is absent from
``terminal_results``, that child was skipped or left pending rather than known
terminal.

AllOf
-----

``AllOf`` observes every non-terminal direct child on every sample. It continues
until all direct children are terminal.

Rules:

* already-terminal children are not observed again;
* already-terminal child result entries are ``None`` on later observations;
* ``n_decided`` counts direct children with terminal results after the current sample;
* ``n_total`` counts direct children;
* the terminal decision is resolved with ``ALL_OF_DECISION_MONOID`` unless a custom resolver is supplied.

AnyOf
-----

``AnyOf`` observes non-terminal children in mapping order. It stops immediately
when any child returns ``Decision.ACCEPT_H1``.

Rules:

* ``ACCEPT_H1`` short-circuits the composite;
* unobserved or non-terminal child result entries are ``None`` in an early
  terminal result;
* ``ACCEPT_H0`` and ``INCONCLUSIVE`` do not short-circuit;
* if no child accepts H1, the composite continues until all direct children are
  terminal;
* if no child accepts H1 but any child is inconclusive, the final decision is
  ``INCONCLUSIVE``;
* on early terminal output, ``n_decided`` can be less than ``n_total`` because
  some direct children may be unobserved or undecided.

Nested composites
-----------------

Nested composites are stored under their direct mapping key. Their child keys are
not flattened into the parent result.

.. code-block:: python

   criterion = AllOf(
       {
           "primary": sprt(llr=primary_llr),
           "secondary-group": AnyOf(
               {
                   "secondary-a": sprt(llr=secondary_a_llr),
                   "secondary-b": sprt(llr=secondary_b_llr),
               }
           ),
       }
   )

The parent result has direct keys only:

.. code-block:: python

   result.results.keys() == {"primary", "secondary-group"}

Operator overloads
------------------

Montest does not expose ``&`` or ``|`` composition. Use explicit ``AllOf`` and
``AnyOf`` mappings.
