from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import textwrap
import unittest

from pycompat_audit.audit import audit_repository
from pycompat_audit.cli import main


class AuditRepositoryTests(unittest.TestCase):
    def test_matching_metadata_passes(self) -> None:
        with repository(
            requires_python=">=3.11",
            classifiers=("3.11", "3.12", "3.13"),
            ci_versions=("3.11", "3.12", "3.13"),
        ) as root:
            result = audit_repository(root)

        self.assertEqual((), result.issues)

    def test_classifier_without_ci_coverage_warns(self) -> None:
        with repository(
            requires_python=">=3.11",
            classifiers=("3.11", "3.12"),
            ci_versions=("3.11",),
        ) as root:
            result = audit_repository(root)

        self.assertIn("CI003", {issue.code for issue in result.warnings})

    def test_ci_version_outside_declared_range_errors(self) -> None:
        with repository(
            requires_python=">=3.12",
            classifiers=("3.12",),
            ci_versions=("3.11", "3.12"),
        ) as root:
            result = audit_repository(root)

        self.assertIn("CI002", {issue.code for issue in result.errors})

    def test_unquoted_yaml_version_is_preserved(self) -> None:
        with repository(
            requires_python=">=3.10",
            classifiers=("3.10",),
            ci_versions=("3.10",),
            quote_ci_versions=False,
        ) as root:
            result = audit_repository(root)

        self.assertEqual(("3.10",), result.ci_versions)

    def test_strict_cli_fails_on_warning(self) -> None:
        with repository(
            requires_python=">=3.11",
            classifiers=("3.11", "3.12"),
            ci_versions=("3.11",),
        ) as root:
            exit_code = main([str(root), "--strict"])

        self.assertEqual(1, exit_code)


class repository:
    def __init__(
        self,
        *,
        requires_python: str,
        classifiers: tuple[str, ...],
        ci_versions: tuple[str, ...],
        quote_ci_versions: bool = True,
    ) -> None:
        self.requires_python = requires_python
        self.classifiers = classifiers
        self.ci_versions = ci_versions
        self.quote_ci_versions = quote_ci_versions
        self.directory = TemporaryDirectory()

    def __enter__(self) -> Path:
        root = Path(self.directory.name)
        classifier_lines = "\n".join(
            f'  "Programming Language :: Python :: {version}",' for version in self.classifiers
        )
        (root / "pyproject.toml").write_text(
            textwrap.dedent(
                f"""\
                [project]
                name = "example"
                version = "0.1.0"
                requires-python = "{self.requires_python}"
                classifiers = [
                {classifier_lines}
                ]
                """
            ),
            encoding="utf-8",
        )
        workflow_path = root / ".github" / "workflows"
        workflow_path.mkdir(parents=True)
        versions = ", ".join(
            f'"{version}"' if self.quote_ci_versions else version for version in self.ci_versions
        )
        (workflow_path / "ci.yml").write_text(
            textwrap.dedent(
                f"""\
                jobs:
                  test:
                    strategy:
                      matrix:
                        python-version: [{versions}]
                """
            ),
            encoding="utf-8",
        )
        return root

    def __exit__(self, *args: object) -> None:
        self.directory.cleanup()


if __name__ == "__main__":
    unittest.main()
