montest documentation
=====================

Montest is a stochastic testing framework for Python. It tests
non-deterministic systems by evaluating statistical evidence across repeated
observations instead of relying on one-shot binary assertions.

Current scope
-------------

The current package ships the zero-dependency stochastic core:

* sequential sampling helpers;
* sync and async iterators;
* typed observation results;
* stopping criteria;
* Wald SPRT;
* explicit ``AllOf`` and ``AnyOf`` composition.

Testing-tool integrations are intentionally not part of the current package.
Future pytest and behave integrations should live behind optional install
groups only after those adapters exist and are tested.

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
