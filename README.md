# montest

[![CI](https://github.com/BBVA/montest/actions/workflows/ci.yml/badge.svg)](https://github.com/BBVA/montest/actions/workflows/ci.yml)

Montest tests nondeterministic Python behavior by collecting repeated observations
until a stopping criterion reaches a decision, instead of treating one random
outcome as conclusive.

## Core install

The PyPI distribution is not available yet while the project name is being
claimed. Until then, install the dependency-free Montest core from Git:

```bash
pip install "montest @ git+https://github.com/BBVA/montest.git@main"
```

For reproducible environments, replace `main` with a commit SHA.

The base install contains the dependency-free stochastic core and has no runtime
dependencies. Use its sequential iterators and criteria directly when pytest is
not the test runner.

## Pytest workflow

Install the explicit optional adapter from the same Git repository:

```bash
pip install "montest[pytest] @ git+https://github.com/BBVA/montest.git@main"
```

`import montest` remains dependency-free and does not import pytest. The adapter
is `montest.pytest`; it installs no plugin, marker, decorator, or injected
fixture. Define an ordinary fixture for raw samples, create a fresh criterion
for each test, turn each raw sample into one domain observation, and assert the
named domain decision:

```python
import pytest

from montest import Decision
from montest.pytest import CachedSamples, cached_samples, stochastic

NO_BIAS_DETECTED = Decision.ACCEPT_H0


@pytest.fixture(scope="session")
def samples() -> CachedSamples[bool]:
    return cached_samples(read_one_flip)


def test_coin_has_no_bias(samples: CachedSamples[bool]) -> None:
    with stochastic(samples, detect_coin_bias()) as run:
        for raw_flip in run:
            run.observe(raw_flip is True)

    run.assert_decision(NO_BIAS_DETECTED)
```

The fixture controls cache lifetime; the test body controls the domain
transformation. `ACCEPT_H0` supports the configured acceptable model over the
chosen concerning alternative, `ACCEPT_H1` reports the concerning behavior, and
`INCONCLUSIVE` means the configured sample budget ended first.

Read the [pytest developer guide](docs/integrations.rst) before configuring a
criterion. For complete progressive, runnable tests, start with
[examples/pytest/README.md](examples/pytest/README.md), then the
[coin](examples/pytest/tests/test_coin_fairness.py),
[dice](examples/pytest/tests/test_dice_fairness.py),
[roulette](examples/pytest/tests/test_roulette_fairness.py), and
[LLM](examples/pytest/tests/test_llm_emoji.py) modules. The adapter is
synchronous; Behave support remains planned only.

## Documentation

Build local documentation with:

```bash
task docs
```

## Development Setup

### Prerequisites (without Nix)

You will need the following tools installed on your system:

- **Python 3.11, 3.12, 3.13, and 3.14** — all four versions must be discoverable on `$PATH` as `python3.11`, `python3.12`, `python3.13`, and `python3.14`
- **[uv](https://docs.astral.sh/uv/)** — fast Python package and project manager
- **[Task](https://taskfile.dev/)** (`go-task`) — task runner used to execute all CI steps

Once the tools are available, install the project dependencies:

```bash
task sync
```

Then run individual workflow steps:

```bash
task lint
task typecheck
task test
task test TOX_ENV=py313
```

### Prerequisites (with Nix)

If you have [Nix](https://nixos.org/) with [flakes](https://nixos.wiki/wiki/Flakes) enabled, the dev shell provides all required tools:

```bash
nix develop
```

The same `task` commands apply in that shell.

## License

Copyright 2026 Banco Bilbao Vizcaya Argentaria, S.A.

Licensed under the [Apache License, Version 2.0](https://www.apache.org/licenses/LICENSE-2.0).
See the [NOTICE](NOTICE) file for additional attribution information.
