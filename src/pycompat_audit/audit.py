from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
import tomllib
from typing import Any

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError


PYTHON_CLASSIFIER_PREFIX = "Programming Language :: Python :: "
MINOR_VERSION_PATTERN = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)(?:\.\d+)?$")


@dataclass(frozen=True)
class AuditIssue:
    severity: str
    code: str
    message: str
    path: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class AuditResult:
    issues: tuple[AuditIssue, ...]
    classifiers: tuple[str, ...]
    ci_versions: tuple[str, ...]
    requires_python: str | None

    @property
    def errors(self) -> tuple[AuditIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "error")

    @property
    def warnings(self) -> tuple[AuditIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "warning")

    def as_dict(self) -> dict[str, object]:
        return {
            "requires_python": self.requires_python,
            "classifiers": list(self.classifiers),
            "ci_versions": list(self.ci_versions),
            "issues": [issue.as_dict() for issue in self.issues],
            "summary": {
                "errors": len(self.errors),
                "warnings": len(self.warnings),
            },
        }


def audit_repository(root: str | Path) -> AuditResult:
    root = Path(root).resolve()
    issues: list[AuditIssue] = []
    pyproject_path = root / "pyproject.toml"
    pyproject = _load_pyproject(pyproject_path, issues)
    project = pyproject.get("project", {})

    if not isinstance(project, dict):
        issues.append(
            AuditIssue("error", "META001", "[project] must be a TOML table.", "pyproject.toml")
        )
        project = {}

    requires_python = project.get("requires-python")
    if not isinstance(requires_python, str) or not requires_python.strip():
        issues.append(
            AuditIssue(
                "error",
                "META002",
                "Declare [project].requires-python so installers know the supported range.",
                "pyproject.toml",
            )
        )
        requires_python = None

    specifier = _parse_specifier(requires_python, issues)
    classifiers = _extract_classifiers(project)
    if not classifiers:
        issues.append(
            AuditIssue(
                "warning",
                "META003",
                "Add minor-version Python classifiers to publish an explicit support contract.",
                "pyproject.toml",
            )
        )

    ci_versions = _extract_ci_versions(root / ".github" / "workflows", issues)
    if not ci_versions:
        issues.append(
            AuditIssue(
                "warning",
                "CI001",
                "No explicit setup-python versions were found in .github/workflows.",
                ".github/workflows",
            )
        )

    if specifier is not None:
        for version in classifiers:
            if not _specifier_allows_minor(specifier, version):
                issues.append(
                    AuditIssue(
                        "error",
                        "META004",
                        f"Classifier Python {version} is outside requires-python {requires_python!r}.",
                        "pyproject.toml",
                    )
                )
        for version in ci_versions:
            if not _specifier_allows_minor(specifier, version):
                issues.append(
                    AuditIssue(
                        "error",
                        "CI002",
                        f"CI tests Python {version}, which is outside requires-python {requires_python!r}.",
                        ".github/workflows",
                    )
                )

    for version in sorted(set(classifiers) - set(ci_versions), key=_version_key):
        issues.append(
            AuditIssue(
                "warning",
                "CI003",
                f"Classifier Python {version} is not covered by an explicit CI test version.",
                ".github/workflows",
            )
        )

    for version in sorted(set(ci_versions) - set(classifiers), key=_version_key):
        issues.append(
            AuditIssue(
                "warning",
                "META005",
                f"CI tests Python {version}, but pyproject.toml has no matching classifier.",
                "pyproject.toml",
            )
        )

    return AuditResult(
        issues=tuple(issues),
        classifiers=tuple(sorted(classifiers, key=_version_key)),
        ci_versions=tuple(sorted(ci_versions, key=_version_key)),
        requires_python=requires_python,
    )


def _load_pyproject(path: Path, issues: list[AuditIssue]) -> dict[str, Any]:
    if not path.is_file():
        issues.append(AuditIssue("error", "META000", "pyproject.toml was not found.", "pyproject.toml"))
        return {}
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        issues.append(AuditIssue("error", "META000", f"Could not read pyproject.toml: {exc}", "pyproject.toml"))
        return {}
    return data


def _parse_specifier(
    requires_python: str | None, issues: list[AuditIssue]
) -> SpecifierSet | None:
    if requires_python is None:
        return None
    try:
        return SpecifierSet(requires_python)
    except InvalidSpecifier as exc:
        issues.append(
            AuditIssue(
                "error",
                "META002",
                f"Invalid [project].requires-python value: {exc}",
                "pyproject.toml",
            )
        )
        return None


def _extract_classifiers(project: dict[str, Any]) -> set[str]:
    raw_classifiers = project.get("classifiers", [])
    if not isinstance(raw_classifiers, list):
        return set()
    versions = set()
    for classifier in raw_classifiers:
        if not isinstance(classifier, str) or not classifier.startswith(PYTHON_CLASSIFIER_PREFIX):
            continue
        version = _normalize_minor(classifier.removeprefix(PYTHON_CLASSIFIER_PREFIX))
        if version:
            versions.add(version)
    return versions


def _extract_ci_versions(workflows_path: Path, issues: list[AuditIssue]) -> set[str]:
    if not workflows_path.is_dir():
        return set()

    versions: set[str] = set()
    for path in sorted((*workflows_path.glob("*.yml"), *workflows_path.glob("*.yaml"))):
        try:
            workflow = YAML(typ="base").load(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, YAMLError) as exc:
            issues.append(
                AuditIssue(
                    "error",
                    "CI000",
                    f"Could not parse workflow YAML: {exc}",
                    path.as_posix(),
                )
            )
            continue
        versions.update(_find_python_versions(workflow))
    return versions


def _find_python_versions(value: Any) -> set[str]:
    versions: set[str] = set()
    if isinstance(value, dict):
        for key, nested_value in value.items():
            if key == "python-version":
                versions.update(_minor_versions_from_value(nested_value))
            else:
                versions.update(_find_python_versions(nested_value))
    elif isinstance(value, list):
        for item in value:
            versions.update(_find_python_versions(item))
    return versions


def _minor_versions_from_value(value: Any) -> set[str]:
    if isinstance(value, list):
        return {version for item in value if (version := _normalize_minor(item))}
    version = _normalize_minor(value)
    return {version} if version else set()


def _normalize_minor(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    match = MINOR_VERSION_PATTERN.match(value.strip())
    if not match:
        return None
    return f"{int(match.group('major'))}.{int(match.group('minor'))}"


def _specifier_allows_minor(specifier: SpecifierSet, version: str) -> bool:
    try:
        return Version(f"{version}.0") in specifier
    except InvalidVersion:
        return False


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))
