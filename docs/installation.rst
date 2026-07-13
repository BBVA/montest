Installation
============

Core install
------------

Install the dependency-free Montest core:

.. code-block:: bash

   pip install montest

The base package contains decisions, observation results, stopping criteria,
sequential iterators, SPRT, and explicit composites. It has no runtime
dependencies.

pytest adapter
--------------

Install the optional synchronous pytest adapter in the environment that runs
your tests:

.. code-block:: bash

   pip install "montest[pytest]"

Import its public constructors from ``montest.pytest``. Plain ``import
montest`` remains dependency-free and does not import pytest. The adapter adds
no plugin, marker, decorator, or injected fixture: declare normal pytest
fixtures for raw samples and use the explicit run in the test body.

Read :doc:`integrations` for the developer workflow, cache scope, decisions,
and failure behavior. The complete progressive examples are in
`examples/pytest/README.md <../examples/pytest/README.md>`_.

Development setup
-----------------

Install development dependencies with the repository task runner:

.. code-block:: bash

   task sync

Common local checks:

.. code-block:: bash

   task lint
   task typecheck
   task test
   task docs

Nix development shell
---------------------

If Nix flakes are enabled, enter the dev shell first:

.. code-block:: bash

   nix develop

The shell provides ``uv``, ``task``, and supported Python versions. The same
``task`` commands apply inside the shell.

Documentation tooling
---------------------

Sphinx is a development dependency, not a runtime dependency of the base
package.

Future integration extras
-------------------------

Behave support remains planned only. ``montest[behave]`` is not available.
