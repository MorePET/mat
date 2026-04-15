"""
Pytest configuration and fixtures for pymat tests.
"""

import pytest

import pymat
from pymat import registry


@pytest.fixture(autouse=True)
def clear_registry():
    """Clear registry and loaded categories before each test to avoid cross-test pollution."""
    registry.clear()
    pymat._LOADED_CATEGORIES.clear()
    yield
    registry.clear()
    pymat._LOADED_CATEGORIES.clear()


@pytest.fixture
def sample_material():
    """Provide a simple test material."""
    from pymat import Material

    return Material(name="Test Material", density=2.5)


@pytest.fixture
def steel_hierarchy():
    """Provide a steel hierarchy for testing."""
    from pymat import Material

    steel = Material(name="Steel", density=7.85)
    s304 = steel.grade_("304", name="SS 304", density=8.0)
    s316L = steel.grade_("316L", name="SS 316L", density=8.0)

    return {
        "root": steel,
        "s304": s304,
        "s316L": s316L,
    }


@pytest.fixture
def scintillator_hierarchy():
    """Provide a scintillator hierarchy."""
    from pymat import Material

    lyso = Material(name="LYSO", density=7.1, formula="Lu1.8Y0.2SiO5")
    lyso_ce = lyso.variant_("Ce", name="LYSO:Ce")
    lyso_sg = lyso_ce.vendor_("saint_gobain", name="Saint-Gobain LYSO:Ce")

    return {
        "root": lyso,
        "ce": lyso_ce,
        "vendor": lyso_sg,
    }
