# Contributing

Thanks for helping improve `pycompat-audit`.

## Development setup

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
pycompat-audit --strict .
```

## Pull requests

- Keep each pull request focused on one behavior change.
- Add or update tests for user-visible behavior.
- Update the README when a command or reported check changes.
- Use clear commit messages.

## Reporting bugs

Open a GitHub issue with a minimal `pyproject.toml`, the relevant workflow
snippet, the command you ran, and the unexpected output.

