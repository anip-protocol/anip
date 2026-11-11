"""A plain ``pip install anip-mcp`` must be importable.

Every third-party module the package imports has to be installed by the
package's own declared dependencies, directly or through their dependencies.
Other test modules cannot catch a missing declaration, because the test
environment installs sibling packages (for example anip-fastapi) that bring
the missing distribution along.
"""
from __future__ import annotations

import ast
import re
import sys
import tomllib
from importlib import metadata
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def _canonical(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _requirement_name(requirement: str) -> str:
    match = re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", requirement.strip())
    assert match, f"unparseable requirement: {requirement!r}"
    return _canonical(match.group(0))


def _imported_third_party_modules() -> set[str]:
    modules: set[str] = set()
    for path in (PACKAGE_ROOT / "src" / "anip_mcp").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                modules.add(node.module.split(".")[0])
    return modules - set(sys.stdlib_module_names) - {"anip_mcp"}


def _distributions_installed_by(requirements: list[str]) -> set[str]:
    """Declared requirements plus everything they depend on."""
    installed: set[str] = set()
    pending = [_requirement_name(requirement) for requirement in requirements]
    while pending:
        name = pending.pop()
        if name in installed:
            continue
        installed.add(name)
        try:
            dependencies = metadata.requires(name) or []
        except metadata.PackageNotFoundError:
            continue
        pending.extend(
            _requirement_name(dependency)
            for dependency in dependencies
            if "extra ==" not in dependency
        )
    return installed


def test_declared_dependencies_install_every_imported_module():
    pyproject = tomllib.loads((PACKAGE_ROOT / "pyproject.toml").read_text())
    installed = _distributions_installed_by(pyproject["project"]["dependencies"])
    providers = metadata.packages_distributions()

    missing = sorted(
        module
        for module in _imported_third_party_modules()
        if not any(_canonical(dist) in installed for dist in providers.get(module, []))
    )

    assert missing == [], (
        f"anip_mcp imports {missing}, but no dependency declared in "
        "pyproject.toml installs them"
    )
