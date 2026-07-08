Composition
===========

Montest composes criteria explicitly with ``AllOf`` and ``AnyOf``. Composite
keys are owned by the mapping passed to the composite, not by child criteria.

Default resolver
----------------

When a composite reaches a terminal state, the default resolver applies this
order:

.. code-block:: python

   if any(decision is Decision.ACCEPT_H1 for decision in decisions):
       return Decision.ACCEPT_H1
   if any(decision is Decision.INCONCLUSIVE for decision in decisions):
       return Decision.INCONCLUSIVE
   return Decision.ACCEPT_H0

AllOf
-----

``AllOf`` observes every non-terminal direct child on every sample. It continues
until all direct children are terminal.

Rules:

* already-terminal children are not observed again;
* already-terminal child result entries are ``None`` on later observations;
* ``n_decided`` counts direct children terminal after the current sample;
* ``n_total`` counts direct children;
* the terminal decision is resolved from all direct terminal decisions.

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
* on terminal output, ``n_decided`` is ``n_total``.

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
