montest documentation
=====================

Montest is a stochastic testing framework for Python. It evaluates repeated
nondeterministic observations until a stopping criterion can make a decision,
rather than treating a one-shot binary assertion as conclusive.

Current scope
-------------

The package ships a dependency-free core with sequential sampling helpers,
synchronous and asynchronous iterators, typed observation results, stopping
criteria, Wald SPRT, and explicit ``AllOf``/``AnyOf`` composition.

For pytest users, the optional ``montest[pytest]`` extra provides the explicit,
synchronous ``montest.pytest`` adapter. It does not change plain ``import
montest`` and it installs no pytest plugin or injected fixture. Start with the
:doc:`pytest developer guide <integrations>` and the complete runnable
`examples/pytest guide <../examples/pytest/README.md>`_. Behave support is
planned only.

.. toctree::
   :maxdepth: 2

   installation
   quickstart
   concepts
   sprt
   composition
   iterators
   integrations
   testing
   api
