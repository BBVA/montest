# montest

[![CI](https://github.com/BBVA/montest/actions/workflows/ci.yml/badge.svg)](https://github.com/BBVA/montest/actions/workflows/ci.yml)

A stochastic BDD framework for Python designed to test non-deterministic systems (e.g., LLMs) by evaluating statistical distributions rather than binary outcomes.

## License

Copyright 2026 Banco Bilbao Vizcaya Argentaria, S.A.

Licensed under the [Apache License, Version 2.0](https://www.apache.org/licenses/LICENSE-2.0).
See the [NOTICE](NOTICE) file for additional attribution information.

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

Then you can run the individual workflow steps:

```bash
task lint        # ruff linter
task typecheck   # mypy type checker
task test        # run tests with the default tox env (py311)
task test TOX_ENV=py313  # run tests against a specific Python version
```

### Prerequisites (with Nix)

If you have [Nix](https://nixos.org/) with [flakes](https://nixos.wiki/wiki/Flakes) enabled, all required tools are provided automatically by the dev shell — no manual installation needed:

```bash
nix develop
```

This drops you into a shell that has `uv`, `task`, and Python 3.11–3.14 all ready to use. The same `task` commands above apply once you are inside the dev shell.
