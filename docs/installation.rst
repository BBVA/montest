Installation
============

Core install
------------

Install Montest with pip:

.. code-block:: bash

   pip install montest

The base install has no runtime dependencies. It contains only the stochastic
core: decisions, observation results, stopping criteria, sequential iterators,
SPRT, and explicit composites.

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

The shell provides ``uv``, ``task``, and the supported Python versions. The same
``task`` commands apply inside the shell.

Documentation tooling
---------------------

Sphinx is a development dependency. It is not a runtime dependency of the base
package.

Future integration extras
-------------------------

pytest and behave integrations are planned but not present. Do not document or
use runnable ``montest[pytest]`` or ``montest[behave]`` install commands until
those adapters exist.
