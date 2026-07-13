SPRT
====

The Sequential Probability Ratio Test accumulates log-likelihood ratios across
observations. Positive cumulative evidence supports H1. Negative cumulative
evidence supports H0.

Construction
------------

.. code-block:: python

   sprt(
       *,
       llr: Callable[[S], float],
       alpha: float = 0.05,
       beta: float = 0.10,
       max_samples: int | None = None,
   )

Parameters:

* ``llr``: per-sample log-likelihood ratio;
* ``alpha``: nominal Type I error target used to construct the approximate Wald
  thresholds;
* ``beta``: nominal Type II error target used to construct the approximate Wald
  thresholds;
* ``max_samples``: optional finite cap.

Wald bounds
-----------

Montest computes Wald bounds as:

.. code-block:: python

   lower = math.log(beta / (1.0 - alpha))
   upper = math.log((1.0 - beta) / alpha)

Decision rules:

* ``cumulative_llr >= upper`` returns ``Decision.ACCEPT_H1``;
* ``cumulative_llr <= lower`` returns ``Decision.ACCEPT_H0``;
* reaching ``max_samples`` inside the bounds returns ``Decision.INCONCLUSIVE``;
* otherwise the result is ``Decision.CONTINUE``.

Approximation and model assumptions
-----------------------------------

The Wald threshold formulas are approximations, not unconditional exact
alpha/beta guarantees. In particular, a discrete observation can cross a boundary
by more than the threshold (boundary overshoot), so the nominal targets do not by
themselves determine exact operating error probabilities. A finite
``max_samples`` can instead produce ``Decision.INCONCLUSIVE``.

The caller remains responsible for supplying a likelihood-ratio process whose
modeling assumptions hold for the observations—for example, correctly specified
within-test iid observations or another explicitly valid conditional model.
Montest does not validate those assumptions or guarantee the resulting operating
characteristics.

Result fields
-------------

``SPRTResult`` includes the base observation fields plus:

* ``cumulative_llr``;
* ``lower_bound``;
* ``upper_bound``;
* ``n_observed``.

Bernoulli LLR example
---------------------

.. code-block:: python

   import math
   from collections.abc import Callable


   def bernoulli_llr(p0: float, p1: float) -> Callable[[int], float]:
       success = math.log(p1 / p0)
       failure = math.log((1.0 - p1) / (1.0 - p0))

       def llr(sample: int) -> float:
           return success if sample else failure

       return llr

Numerical responsibility
------------------------

``llr`` must return finite floats. Montest executes the sequential test mechanics;
it does not validate that the caller's statistical model is appropriate for the
system under test.
