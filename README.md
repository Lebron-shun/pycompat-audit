# pycompat-audit

`pycompat-audit` catches drift between a Python package's declared support and
the versions it actually tests in GitHub Actions.

Python maintainers often update one compatibility signal and miss another:

- `[project].requires-python`
- `Programming Language :: Python :: 3.x` classifiers
- the `actions/setup-python` CI matrix

`pycompat-audit` compares those signals and returns a CI-friendly exit code.

## Install

```bash
python -m pip install pycompat-audit
```

For local development:

```bash
python -m pip install -e .
```

## Use

Run the audit from a repository root:

```bash
pycompat-audit --strict .
```

Example finding:

```text
WARNING CI003 .github/workflows: Classifier Python 3.13 is not covered by an explicit CI test version.
```

Use JSON when another tool needs to consume the result:

```bash
pycompat-audit --format json .
```

## Use the GitHub Action

Add this job to a workflow:

```yaml
jobs:
  compatibility-contract:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - uses: Lebron-shun/pycompat-audit@v0.2.0
```

Warnings fail the workflow by default. To report warnings without failing:

```yaml
- uses: Lebron-shun/pycompat-audit@v0.2.0
  with:
    strict: "false"
```

## What the first release checks

- A `pyproject.toml` file exists and declares `[project].requires-python`.
- Minor-version Python classifiers stay inside the declared range.
- Explicit GitHub Actions Python versions stay inside the declared range.
- Each minor-version classifier has explicit CI coverage.
- Each explicitly tested CI version has a matching classifier.

The audit intentionally stays narrow. It reports compatibility contract drift;
it does not try to replace a test runner, build backend, or linter.

## Roadmap

- Support `tox`, `nox`, and `uv` matrices.
- Offer opt-in checks for Python release and end-of-life dates.
- Publish SARIF output for GitHub code scanning.

## Contributing

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) before
opening a pull request.

## License

MIT
