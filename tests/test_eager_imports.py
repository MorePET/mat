"""Eager-import smoke for every public pymat + mat_vis_client submodule.

Closes the gap that let mat-vis-client 0.5.0's `StrEnum` import (3.10
incompatible) escape py-mat's CI in April 2026: py-mat lazy-imports
``mat_vis_client`` only inside ``Vis._fetch``, so the broken
``mat_vis_client.schema`` module was never loaded by any test on 3.10.
build123d's CI imports ``mat_vis_client.adapters`` eagerly at test-
collection time and blew up; ours stayed green.

This test walks every public submodule of both packages and imports it,
turning the failure-on-touch into a failure at every CI run. Fast
(sub-second), no maintenance — ``pkgutil.walk_packages`` enumerates
dynamically.

Scope:

- pymat — every public submodule (lazy-loaded categories included)
- mat_vis_client — every public submodule (we coordinate releases with
  this dep; downstream consumers import these eagerly)

NOT in scope: ``pint`` / ``periodictable`` / ``uncertainties`` — mature
deps with their own test suites; we'd be testing other people's CI.
"""

from __future__ import annotations

import importlib
import pkgutil

import pytest


def _public_submodules(pkg_name: str) -> list[str]:
    """Enumerate every importable submodule of ``pkg_name``,
    excluding underscore-prefixed (private) ones at any depth."""
    pkg = importlib.import_module(pkg_name)
    pkg_path = getattr(pkg, "__path__", None)
    if pkg_path is None:
        return [pkg_name]  # not a package, just a module

    found = [pkg_name]
    for module_info in pkgutil.walk_packages(pkg_path, prefix=f"{pkg_name}."):
        # Skip private / internal modules — they're allowed to break
        # in ways that would never surface to a public consumer.
        parts = module_info.name.split(".")
        if any(p.startswith("_") for p in parts):
            continue
        found.append(module_info.name)
    return sorted(found)


# Compute the lists at collection time so pytest -v shows each module.
PYMAT_MODULES = _public_submodules("pymat")
MAT_VIS_CLIENT_MODULES = _public_submodules("mat_vis_client")


@pytest.mark.parametrize("module_name", PYMAT_MODULES)
def test_pymat_submodule_imports(module_name):
    """Every public ``pymat.*`` submodule imports cleanly.

    Catches: ``ImportError`` from broken syntax / Python-version-
    specific imports / circular deps / missing optional deps that got
    reached at module load time.
    """
    importlib.import_module(module_name)


@pytest.mark.parametrize("module_name", MAT_VIS_CLIENT_MODULES)
def test_mat_vis_client_submodule_imports(module_name):
    """Every public ``mat_vis_client.*`` submodule imports cleanly.

    Coordinated with mat-vis-client release cadence — a regression in
    a submodule we don't directly use (``schema``, ``adapters``) still
    breaks downstream consumers like build123d that import them
    eagerly. Pinned here so the next bad release fails our CI before
    landing on PyPI users.
    """
    importlib.import_module(module_name)


def test_at_least_some_pymat_modules_found():
    """Sanity: ``walk_packages`` actually found the expected packages.

    Defends against a future refactor that accidentally hides
    submodules behind a custom ``__path__`` or strips ``__init__.py``,
    which would silently zero out the test matrix above."""
    assert len(PYMAT_MODULES) >= 5, f"Only found {len(PYMAT_MODULES)} pymat modules"
    assert "pymat" in PYMAT_MODULES
    assert "pymat.vis" in PYMAT_MODULES


def test_at_least_some_mat_vis_client_modules_found():
    assert len(MAT_VIS_CLIENT_MODULES) >= 2, (
        f"Only found {len(MAT_VIS_CLIENT_MODULES)} mat_vis_client modules"
    )
    assert "mat_vis_client" in MAT_VIS_CLIENT_MODULES
    # At least one of these submodules should exist post-0.6.x — they
    # are exactly the modules build123d's CI imports eagerly.
    submodules = set(MAT_VIS_CLIENT_MODULES) - {"mat_vis_client"}
    assert submodules, "no mat_vis_client submodules found — refactor regression?"
