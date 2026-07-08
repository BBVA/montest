Quick start
===========

This example uses a Bernoulli SPRT. The null hypothesis is ``p = 0.3`` and the
alternative hypothesis is ``p = 0.6``.

.. code-block:: python

   import math
   import random

   from montest import Decision, SequentialIterator, sprt


   def bernoulli_llr(value: int) -> float:
       return math.log(0.6 / 0.3) if value else math.log(0.4 / 0.7)


   rng = random.Random(42)
   criterion = sprt(llr=bernoulli_llr, alpha=0.05, beta=0.10)

   for sample in SequentialIterator(lambda: int(rng.random() < 0.6), criterion):
       print(sample.index, sample.value, sample.decision.value)
       if sample.decision is not Decision.CONTINUE:
           break

Each yielded result records:

* ``index``: the zero-based observation index;
* ``value``: the generated sample;
* ``decision``: the current decision.

SPRT results also expose:

* ``cumulative_llr``;
* ``lower_bound``;
* ``upper_bound``;
* ``n_observed``.
