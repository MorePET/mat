"""Tests for the trailing-`_` chainable-method rename + deprecation
aliases (Bernhard's py-mat #218 readability ask).

Each old name (``grade_``, ``temper_``, ``treatment_``, ``vendor_``,
``variant_``) survives as a deprecation alias that:

1. Emits :class:`DeprecationWarning` with the new name in the message.
2. Returns the same value the new method would have returned.
3. Mutates state identically to the new method.

Removed in 4.0.
"""

from __future__ import annotations

import warnings

import pytest

from pymat.core import Material


@pytest.fixture
def base() -> Material:
    return Material("steel", density=7.85)


class TestAddVerbForms:
    """The new (PEP-clean) method names must be the canonical surface."""

    def test_add_grade_creates_child(self, base):
        s316 = base.add_grade("s316L", density=8.0)
        assert s316.grade == "s316L"
        assert s316.parent is base

    def test_add_temper_creates_child(self, base):
        t6 = base.add_temper("T6")
        assert t6.temper == "T6"

    def test_add_treatment_creates_child(self, base):
        ep = base.add_treatment("electropolished")
        assert ep.treatment == "electropolished"

    def test_add_vendor_creates_child(self, base):
        v = base.add_vendor("saint_gobain")
        assert v.vendor == "saint_gobain"

    def test_add_variant_creates_child(self, base):
        v = base.add_variant("ce_doped")
        assert v.parent is base


class TestDeprecatedAliases:
    """Old trailing-`_` forms still work, but now warn."""

    @pytest.mark.parametrize(
        ("old_name", "new_name"),
        [
            ("grade_", "add_grade"),
            ("temper_", "add_temper"),
            ("treatment_", "add_treatment"),
            ("vendor_", "add_vendor"),
            ("variant_", "add_variant"),
        ],
    )
    def test_alias_warns_and_points_to_new_name(self, base, old_name, new_name):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            getattr(base, old_name)("x")

        deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert deprecations, f"{old_name} did not emit DeprecationWarning"
        msg = str(deprecations[0].message)
        assert old_name in msg
        assert new_name in msg
        assert "4.0" in msg

    def test_alias_returns_same_shape_as_new(self, base):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            old = base.grade_("s316_old")
        new = base.add_grade("s316_new")
        # Both must be Material-shaped children with grade set.
        assert old.grade == "s316_old"
        assert new.grade == "s316_new"
        assert type(old) is type(new)

    def test_alias_state_mutation_matches(self, base):
        # Calling the alias must register the child in the parent's
        # _children map identically to the new method.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            base.temper_("T6_old")
        base.add_temper("T6_new")
        assert "T6_old" in base._children
        assert "T6_new" in base._children


class TestStacklevel:
    """``stacklevel=2`` → warning points at the caller, not the alias
    body. Without this, IDE quick-fixes / pytest output get noisy."""

    def test_warning_filename_is_caller(self, base):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            base.grade_("s")  # this line is the caller
        deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert deprecations
        # The warning's filename should be this test file, not core.py.
        assert deprecations[0].filename.endswith("test_chainable_rename.py")
