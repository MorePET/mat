"""Tests for ``scripts/check_pep_naming.py`` — the custom PEP-8 hook
that flags trailing-single-underscore names whose stripped form isn't
a keyword or built-in.

The hook is a stdlib-only AST walker; tests are also stdlib-only.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_HOOK_PATH = _REPO / "scripts" / "check_pep_naming.py"


def _load_hook():
    spec = importlib.util.spec_from_file_location("check_pep_naming", _HOOK_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_pep_naming"] = mod
    spec.loader.exec_module(mod)
    return mod


hook = _load_hook()


def _write(tmp_path: Path, src: str) -> Path:
    f = tmp_path / "sample.py"
    f.write_text(src, encoding="utf-8")
    return f


class TestTrailingUnderscoreDetection:
    def test_flags_non_keyword_trailing_underscore(self, tmp_path):
        f = _write(tmp_path, "def grade_(self): pass\n")
        diags = hook.check_path(f)
        assert len(diags) == 1
        assert "grade_" in diags[0]
        assert "PYMAT_TRAILING_UNDERSCORE" in diags[0]

    def test_allows_class_underscore(self, tmp_path):
        # `class` is a Python keyword — `class_` is the textbook PEP 8 case.
        f = _write(tmp_path, "def make(class_): pass\n")
        # Note: this hook only flags function/method *names*, not
        # parameters. Ruff's N803 covers parameter names. So a `def`
        # whose parameter is `class_` should not produce diagnostics.
        diags = hook.check_path(f)
        assert diags == []

    def test_allows_keyword_function_name(self, tmp_path):
        # `def class_(...)` would be flagged by ruff (N802) for being
        # confusing, but our hook is specifically about the
        # trailing-`_` rule — and `class` is a keyword, so the
        # trailing underscore IS legitimate per PEP 8. Hook stays out.
        f = _write(tmp_path, "def class_(): pass\n")
        diags = hook.check_path(f)
        assert diags == []

    def test_allows_builtin_function_name(self, tmp_path):
        # `type`, `id`, `list`, `dict` — common shadow targets.
        f = _write(tmp_path, "def type_(): pass\ndef id_(): pass\ndef list_(): pass\n")
        diags = hook.check_path(f)
        assert diags == []

    def test_skips_dunder(self, tmp_path):
        f = _write(tmp_path, "def __init_subclass__(cls): pass\n")
        diags = hook.check_path(f)
        assert diags == []

    def test_skips_leading_underscore_private(self, tmp_path):
        # Single-leading-underscore names — private. Trailing here is
        # weird but it's a different lint axis; PEP 8 doesn't speak
        # to it. Hook stays out.
        f = _write(tmp_path, "def _grade_(self): pass\n")
        diags = hook.check_path(f)
        assert diags == []

    def test_no_underscore_no_flag(self, tmp_path):
        f = _write(tmp_path, "def add_grade(self, key): pass\n")
        diags = hook.check_path(f)
        assert diags == []


class TestSuppression:
    def test_short_form_keep_directive(self, tmp_path):
        f = _write(
            tmp_path,
            "def grade_(self): pass  # pymat-keep-_\n",
        )
        diags = hook.check_path(f)
        assert diags == []

    def test_long_form_quality_directive(self, tmp_path):
        f = _write(
            tmp_path,
            "def grade_(self): pass  # pymat-quality: ignore trailing-underscore\n",
        )
        diags = hook.check_path(f)
        assert diags == []

    def test_legacy_noqa_form(self, tmp_path):
        # Back-compat with the early call sites (not used post-rename
        # in the codebase, but kept recognized so churn is contained).
        f = _write(
            tmp_path,
            "def grade_(self): pass  # noqa: PYMAT_TRAILING_UNDERSCORE\n",
        )
        diags = hook.check_path(f)
        assert diags == []

    def test_unrelated_comment_does_not_suppress(self, tmp_path):
        f = _write(tmp_path, "def grade_(self): pass  # legacy method\n")
        diags = hook.check_path(f)
        assert len(diags) == 1


class TestIntegration:
    def test_main_returns_0_on_clean_file(self, tmp_path):
        clean = tmp_path / "clean.py"
        clean.write_text("def add_grade(self, key): pass\n", encoding="utf-8")
        rc = hook.main([str(clean)])
        assert rc == 0

    def test_main_returns_1_on_violation(self, tmp_path, capsys):
        bad = tmp_path / "bad.py"
        bad.write_text("def grade_(self): pass\n", encoding="utf-8")
        rc = hook.main([str(bad)])
        assert rc == 1
        out = capsys.readouterr().out
        assert "grade_" in out

    def test_walks_directories(self, tmp_path):
        sub = tmp_path / "nested"
        sub.mkdir()
        (sub / "a.py").write_text("def grade_(self): pass\n", encoding="utf-8")
        (sub / "b.py").write_text("def add_grade(self): pass\n", encoding="utf-8")
        rc = hook.main([str(tmp_path)])
        assert rc == 1

    def test_repo_is_clean(self):
        """The codebase itself must pass. Regression guard against
        accidentally re-introducing trailing-`_` methods without a
        deprecation directive."""
        rc = hook.main(["src", "tests", "scripts"])
        assert rc == 0


class TestSyntaxError:
    def test_reports_syntax_error_does_not_crash(self, tmp_path):
        bad = _write(tmp_path, "def broken(\n")
        diags = hook.check_path(bad)
        assert any("SyntaxError" in d for d in diags)


@pytest.mark.parametrize(
    ("name", "expected_violation"),
    [
        ("grade_", True),
        ("temper_", True),
        ("treatment_", True),
        ("vendor_", True),
        ("variant_", True),
        ("class_", False),
        ("type_", False),
        ("id_", False),
        ("dict_", False),
        ("list_", False),
        ("set_", False),
        ("input_", False),
        ("filter_", False),
        ("format_", False),
        ("from_", False),
        ("add_grade", False),
        ("__init__", False),
        ("__call__", False),
    ],
)
def test_known_names(tmp_path, name, expected_violation):
    f = _write(tmp_path, f"def {name}(self): pass\n")
    diags = hook.check_path(f)
    assert bool(diags) == expected_violation, (name, diags)
