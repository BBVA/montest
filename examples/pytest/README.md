<!--
Copyright 2026 Banco Bilbao Vizcaya Argentaria, S.A.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-->

# Montest pytest examples

These executable examples teach ordinary pytest developers how to test a
stochastic behavior with Montest. You do not need a statistics background to
follow them: begin with a familiar coin, then add two dice conditions, then a
roulette composite, and finally see the same workflow against a live LLM.
They use this checkout through the editable `montest[pytest]` dependency rather
than a published wheel.

## Setup and commands

From this directory:

```console
uv sync
uv run python runner.py list
uv run python runner.py run offline -q
```

`offline` runs the coin, dice, and roulette scenarios. It makes **no external
service calls**. Its report contains both passing expected-behavior tests and
strict-xfailed known-defect demonstrations.

The live LLM scenario requires the optional dependency, a credential, network
access, and paid API calls. Use either `GOOGLE_API_KEY` or `GEMINI_API_KEY`:

```console
uv sync --extra llm
GOOGLE_API_KEY=<real-key> uv run --extra llm python runner.py run llm -q
```

With credentials, `all` includes the offline passing/xfailed scenarios plus the
live LLM tests: a passing controlled-prompt test and a strict-xfailed
missing-control-prompt demonstration.

```console
GOOGLE_API_KEY=<real-key> uv run --extra llm python runner.py run all -q
```

The runner also works from another current directory:

```console
uv run --project examples/pytest python examples/pytest/runner.py list
uv run --project examples/pytest python examples/pytest/runner.py run offline -q
```

## Read the examples in order

1. [Coin fairness](tests/test_coin_fairness.py) introduces the loop and one
   binary observation: “was this flip heads?”
2. [Dice fairness](tests/test_dice_fairness.py) maps each raw pair of rolls to
   two related observations and combines the child criteria.
3. [Roulette fairness](tests/test_roulette_fairness.py) shows a three-child
   composite that lets every color criterion receive each spin while resolving
   the wheel-level requirement as concerning when any color is overrepresented.
4. [Live LLM emoji behavior](tests/test_llm_emoji.py) keeps that same test
   shape while samples are paid, networked model responses. Read its warnings
   and setup requirements before running it.

Start with the coin scenario. A normal coin produces heads about 50% of the
time. The test treats 65% heads as a clearly concerning bias; it is not trying
to estimate the coin's exact probability. Each observed head adds evidence for
the concerning behavior and each tail adds evidence for normal behavior.
Sampling stops when enough evidence supports either choice, or when the sample
budget ends.

In Montest terms, the acceptable outcome is **H0** (`Decision.ACCEPT_H0`), and
the undesirable outcome is **H1** (`Decision.ACCEPT_H1`). H1 is a statistical
failure outcome when a test requires H0; it is not a successful undesirable
scenario. The accumulated evidence score is the **log-likelihood ratio**
(LLR): positive evidence favors H1 and negative evidence favors H0.

## What the names mean

The scenario modules classify constants by ownership so a reader can tell what
a change means:

| Name category | Owner and purpose |
| --- | --- |
| Domain requirement | Product/domain policy, named `EXPECTED_*` for acceptable behavior and `CONCERNING_*` for the meaningful deviation to detect. It determines the expected H0 conclusion. |
| Source truth | Deterministic simulator or live-input configuration. Offline sources use `SIMULATED_*`; the LLM sources use `NO_EMOJI_SYSTEM_PROMPT` and `KNOWN_BAD_PROMPT_WITHOUT_EMOJI_CONTROL`. Fair/controlled sources model the requirement; biased or missing-control sources deliberately model a known defect. This is test data, not product policy. |
| Domain outcome | Domain alias for `Decision.ACCEPT_H0`, such as `NO_SELECTED_SIDE_BIAS_DETECTED`, `NO_LOADED_DIE_DETECTED`, `NO_OVERREPRESENTED_COLOR_DETECTED`, or `LOW_EMOJI_RATE_SUPPORTED`. Tests assert this acceptable conclusion rather than expose H0/H1 at the call site. |
| `SPRT_ALPHA` / `SPRT_BETA` | Shared nominal false-alarm and missed-detection targets passed to each SPRT child. They construct approximate Wald thresholds; they are neither source probabilities nor observed error frequencies. |
| Domain-unit budget | A cap named for the sampled unit—`MAXIMUM_FLIPS`, `MAXIMUM_PAIR_ROLLS`, `MAXIMUM_SPINS`, or `MAXIMUM_RESPONSES`—rather than a generic implementation counter. It bounds cost and latency and may yield `Decision.INCONCLUSIVE`. |

The local evidence helper beside each scenario converts a domain observation
into LLR increments. Keeping its logarithm formula beside the audited model
lets the test body say `run.observe(domain_observation)` without duplicating
algebra.

| Term | Meaning in these tests |
| --- | --- |
| Raw sample | Source value: a coin flip, die roll, wheel spin, or model response. |
| Derived observation | Fact sent to the criterion, such as “this flip was heads” or “this response contains emoji.” |
| Criterion | Stopping rule that turns observations into a decision. Create a fresh one for every test. |
| H0 | Chosen acceptable baseline behavior, such as a 50% heads rate. |
| H1 | Chosen undesirable behavior to detect, such as a 65% heads rate. It is the failure outcome when the test requires H0. |
| LLR / evidence score | Running log-likelihood ratio: accumulated support for H1 versus H0. |
| Alpha / false-alarm target | Nominal target for incorrectly flagging H1 when the baseline applies. |
| Beta / missed-detection target | Nominal target for failing to flag H1 when the chosen alternative applies. |
| Inconclusive | The sample budget ended before either decision had enough evidence. |

`SPRT_ALPHA` and `SPRT_BETA` are nominal targets used to construct approximate
Wald thresholds, not exact promises about every run. The gap between acceptable
and undesirable rates defines the two behaviors being compared; it neither
estimates every possible rate nor proves universal fairness. Before running a
test, decide what `Decision.INCONCLUSIVE` means operationally: collect more
data later, investigate manually, or block a release.

## The pytest workflow

Every test uses the same public sequence:

1. A user-defined fixture owns a sample generator. `cached_samples` lets
   independent tests replay an expensive or seeded stream from its beginning.
2. The test constructs a fresh stopping criterion for its acceptable H0 and
   undesirable H1 models.
3. Inside `stochastic(...)`, the test transforms every raw sample into one
   domain observation and submits it with `run.observe(...)`. A composite can
   put several related facts in that one observation, such as both high-roll
   booleans for a pair of dice.
4. When the criterion stops the loop, `run.assert_decision(...)` checks the
   named acceptable domain outcome.

Choose H0 from acceptable behavior and H1 as the smallest operationally
important deviation. Keep generation and configuration fixed during a test.
Use separate caches for distinct distributions—for example, different models,
model versions, prompts, input populations, temperatures, or tool
configurations—and treat cached samples as immutable.

The emoji example compares `LOW_EMOJI_REFERENCE_RATE` with
`CONCERNING_HIGH_EMOJI_RATE` under a fixed prompt and model configuration.
`NO_EMOJI_SYSTEM_PROMPT` is the expected-behavior control.
`KNOWN_BAD_PROMPT_WITHOUT_EMOJI_CONTROL` deliberately demonstrates defect
tracking; it is not an unrestricted calibration or a claim of generic model
noncompliance. Its result is evidence about that configured rate, not proof of
an absolute no-emoji policy.

## Expected behavior and known-defect demonstrations

Ordinary projects normally keep only expected-behavior tests. They do **not**
need to create a broken variant to use Montest or an SPRT. Each such test uses a
requirement-aligned source and asserts one acceptable domain outcome:
`run.assert_decision(Decision.ACCEPT_H0)` (or its domain-named equivalent).

These examples additionally keep targeted known-defect demonstrations. A
known-defect test has the same acceptable requirement and the same single final
assertion as its expected-behavior counterpart. Its deliberately bad source
reaches H1, so that assertion mismatches and causes the xfail; H1 is never the
expected success condition.

The marker is strict:
`pytest.mark.xfail(strict=True, raises=pytest.fail.Exception)`. `strict=True`
turns an XPASS into a failure, so a repaired defect cannot silently leave stale
tracking. `raises=pytest.fail.Exception` limits the xfail to the pytest
assertion failure from the single final assertion. A generator, network,
credential, or API failure remains a real failure rather than being mislabeled
as the known defect. This is normal pytest behavior, not a Montest-specific
xfail mechanism.

Without credentials, the live cases xfail before their sources make a model
call, so no paid request is attempted. Do not treat this as a substitute for
the credentialed live test when verifying a real model.

## Composite results

Some scenarios combine child criteria. An `AnyOf` result, and the roulette
composite result, combine several child decisions rather than describe one
criterion's operating characteristics. Inspect terminal child results where
the module does so; early composite completion can leave other children without
terminal evidence. Children using the same raw samples are correlated, so their
composite has different, uncorrected operating characteristics. Montest does
not apply multiple-testing or family-wise-error corrections.

## Shared samples and statistical independence

Every test gets an independent cursor beginning at cached sample zero, and
differently sized sequential tests replay the same prefix before extending the
shared cache.

Replaying a shared cache does not change an individual test's marginal input
prefix relative to consuming the same process-local stream afresh. It preserves
only the same nominal/approximate operating characteristics the configured
criterion would have had on that stream; it does not create exact alpha/beta
guarantees. For each test, the derived observations passed to the criterion
must satisfy its modeled likelihood-ratio process—typically correctly specified
within-test iid observations or another explicitly valid conditional model—and
generation configuration must remain unchanged. Raw-to-observation mapping,
criterion selection, and cache reuse must be deterministic/fixed before results
and must not adapt to another test's outcome. A finite `max_samples` may
terminate as `Decision.INCONCLUSIVE`.

Tests sharing raw observations are correlated and are not statistically
independent; cursor independence is only execution-state independence. Montest
does not apply multiple-testing/family-wise error corrections.

Use separate fixture instances for different models, model versions, prompts,
input distributions, temperatures, tool configurations, or any other setting
that changes the data-generating distribution. Treat cached objects as
immutable. In-memory session caches are per pytest process, so xdist workers
make separate external calls. Consult statistical expertise before applying
these decisions to safety, regulatory, or other high-impact outcomes.
