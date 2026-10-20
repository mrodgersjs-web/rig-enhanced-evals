# Changelog

All notable changes are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-10-19

- This commit fixes `.github/workflows/ci.yml`, which GitHub rejected as invalid YAML (an unquoted colon in a step name), runs coverage as `coverage run` plus `coverage report` instead of mixing it with `--cov`, and adds `test/test_workflows_parse.py`, which loads every workflow with PyYAML (now in the dev extra) so this cannot recur.

### Added

- `src/runner.py`: dataset loader, runner, and RunReport summariser.
- `src/report.py`: JSON, Markdown, and stdout report writers.
- `src/cli.py`: command-line entry point (`python -m src.cli`).
- `examples/sample-suite.json`: 4-case smoke suite (1 pass + 3 fail).
- `test/test_runner.py`: 12 unit tests for the dataset runner.
- `test/test_report.py`: 5 unit tests for the report writers.
- `test/test_cli.py`: 7 unit tests for the CLI plus an end-to-end
  subprocess test.
- `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`,
  `CHANGELOG.md`, `.github/dependabot.yml`,
  `.github/ISSUE_TEMPLATE/{bug_report,feature_request,config}.yml`,
  `.github/PULL_REQUEST_TEMPLATE.md`.
- Matrix CI on Python 3.10-3.13 with ruff.
- `src/py.typed` marker.
- `CITATION.cff` for the project.

### Changed

- `pyproject.toml` bumped to 0.2.0; requires-python stays >=3.10;
  classifiers add 3.13; project.urls gains Issues and Changelog; dev
  extras gain pytest-cov and ruff; adds a `[tool.ruff]` block.

## [0.1.0] - 2026-09-08

### Added

- Initial release: Evaluator, Verifier, L10Harness, and 9 tests.
