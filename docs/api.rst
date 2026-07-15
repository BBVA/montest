API reference
=============

For the pytest application workflow and normal domain-level assertions, read
:doc:`integrations` before using this reference. Its `runnable examples
<https://github.com/BBVA/montest/tree/main/examples/pytest>`_ provide the
progressive learning path. This page records public symbols and contracts
rather than prescribing feature-test evidence assertions.

Core API
--------

.. autoclass:: montest.Decision
   :members:

.. autoclass:: montest.ObservationResult
   :members:

.. autoclass:: montest.StoppingCriterion
   :members:

.. autoclass:: montest.SequentialIterator
   :members:

.. autoclass:: montest.AsyncSequentialIterator
   :members:

.. autoclass:: montest.AllOf
   :members:

.. autoclass:: montest.AnyOf
   :members:

.. autoclass:: montest.CompositeResult
   :members:

.. autoclass:: montest.DecisionMonoid
   :members:

.. autodata:: montest.ANY_OF_DECISION_MONOID

.. autodata:: montest.ALL_OF_DECISION_MONOID

SPRT
----

.. autoclass:: montest.SPRT
   :members:

.. autoclass:: montest.SPRTResult
   :members:

.. autofunction:: montest.sprt

pytest adapter
--------------

Install ``montest[pytest]`` from Git before importing this optional adapter.
It is not imported by the dependency-free ``montest`` core. The adapter is
synchronous, explicit, and has no pytest plugin or injected fixture; see
:doc:`integrations` for its lifecycle and error contracts.

.. autoclass:: montest.pytest.CachedSamples
   :members:

.. autoclass:: montest.pytest.StochasticRun
   :members:

.. autofunction:: montest.pytest.cached_samples

.. autofunction:: montest.pytest.stochastic
