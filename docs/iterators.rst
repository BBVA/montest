Iterators
=========

Criteria can be observed manually or through sequential iterators.

Manual observation
------------------

.. code-block:: python

   criterion = sprt(llr=llr)
   result = criterion.observe(sample, index=0)

Manual observation is useful when another framework owns the sampling loop.

SequentialIterator
------------------

``SequentialIterator`` accepts a zero-argument generator and a stopping criterion.

Rules:

* indices are zero-based;
* one sample is generated per ``__next__`` call;
* the terminal result is yielded once;
* the next call after a terminal result raises ``StopIteration``.

.. code-block:: python

   for result in SequentialIterator(generate, criterion):
       handle(result)

AsyncSequentialIterator
-----------------------

``AsyncSequentialIterator`` accepts a sync or async zero-argument generator.

.. code-block:: python

   iterator = AsyncSequentialIterator(generate, criterion, concurrency=4)

Rules:

* ``concurrency`` must be at least 1;
* async generators are awaited directly;
* sync generators run through ``asyncio.to_thread``;
* batches are generated with ``asyncio.gather``;
* gathered values are observed in request order, not completion order;
* generated-but-unobserved surplus values are discarded after a terminal decision
  inside a batch.

With ``concurrency > 1``, the generator may be called more times than the number
of yielded results.
