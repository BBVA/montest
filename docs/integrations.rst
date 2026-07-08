Testing-framework integrations
==============================

Current status
--------------

Montest currently ships the zero-dependency stochastic core only. pytest and
behave integrations are planned but not implemented.

This page is contributor-facing. It defines boundaries for future testing
framework adapters; it is not user-facing installation documentation for adapters
that do not exist yet.

Integration boundary
--------------------

A testing-framework integration should:

* depend on the core API;
* not duplicate SPRT logic;
* not change core result semantics;
* map framework-specific outcomes onto ``Decision`` values;
* preserve typed result records;
* make framework dependencies optional;
* keep the base ``montest`` install dependency-free.

Packaging rule
--------------

Future integrations should live behind optional groups only when they exist and
are tested. Planned names include:

* ``montest[pytest]``;
* ``montest[behave]``.

Do not add those extras before the corresponding adapter is implemented.

Adapter design checklist
------------------------

For each integration, answer:

* What is the framework entry point?
* How are repeated observations generated?
* How is a terminal decision reported?
* How are inconclusive outcomes represented?
* How are stochastic traces exposed for debugging?
* How does async behavior fit?
* How are framework errors distinguished from terminal stochastic decisions?
* What is the minimum extra dependency set?

Current non-goals
-----------------

The current package does not include:

* pytest markers or fixtures;
* behave step decorators;
* Gherkin parsing;
* CLI commands;
* report generation;
* feature-file support.
