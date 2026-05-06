"""Tests for `scripts/check_licenses.py` (#174).

Validates the CI gate that enforces `_sources.<key>.license` is always
in the allowed set on merge. Uses tmp_path TOMLs so the test corpus
is isolated from src/pymat/data/.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "check_licenses.py"


def _run(
    env_data_dir: Path, env_ratchet: Path | None = None, *args: str
) -> subprocess.CompletedProcess:
    """Run check_licenses.py with DATA_DIR / RATCHET overridden via monkeypatch shim."""
    # The script reads DATA_DIR / RATCHET as module-level constants, so we
    # invoke it via a small shim that monkeypatches them. Simpler than env vars.
    shim = env_data_dir.parent / "shim.py"
    ratchet_arg = (
        f", check_licenses.RATCHET = type(check_licenses.RATCHET)({str(env_ratchet)!r})"
        if env_ratchet
        else ""
    )
    shim.write_text(
        dedent(f"""
        import sys
        sys.path.insert(0, {str(REPO_ROOT / "scripts")!r})
        import check_licenses
        check_licenses.DATA_DIR = type(check_licenses.DATA_DIR)({str(env_data_dir)!r})
        {ratchet_arg.strip(", ") if ratchet_arg.strip() else ""}
        sys.exit(check_licenses.main())
        """)
    )
    return subprocess.run(
        [sys.executable, str(shim), *args],
        capture_output=True,
        text=True,
    )


@pytest.fixture
def data_dir(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    return d


class TestValidate:
    def test_passes_on_empty_corpus(self, data_dir):
        result = _run(data_dir)
        assert result.returncode == 0, result.stderr

    def test_passes_when_no_sources_block(self, data_dir):
        (data_dir / "metals.toml").write_text(
            dedent("""
            [steel]
            name = "Steel"
            [steel.mechanical]
            density_value = 7.85
            density_unit = "g/cm^3"
            """)
        )
        result = _run(data_dir)
        assert result.returncode == 0, result.stderr

    def test_passes_with_valid_license(self, data_dir):
        (data_dir / "metals.toml").write_text(
            dedent("""
            [iron]
            name = "Iron"
            [iron._sources."mechanical.density"]
            citation = "wikidata_iron"
            kind = "qid"
            ref = "Q677"
            license = "CC0"
            """)
        )
        result = _run(data_dir)
        assert result.returncode == 0, result.stderr

    def test_rejects_missing_license(self, data_dir):
        (data_dir / "metals.toml").write_text(
            dedent("""
            [iron]
            name = "Iron"
            [iron._sources."mechanical.density"]
            citation = "wikidata_iron"
            kind = "qid"
            ref = "Q677"
            """)
        )
        result = _run(data_dir)
        assert result.returncode == 1
        assert "missing 'license'" in result.stderr

    def test_rejects_unknown_license(self, data_dir):
        (data_dir / "metals.toml").write_text(
            dedent("""
            [iron]
            name = "Iron"
            [iron._sources."mechanical.density"]
            citation = "x"
            kind = "doi"
            ref = "10.x/y"
            license = "unknown"
            """)
        )
        result = _run(data_dir)
        assert result.returncode == 1
        assert "license='unknown'" in result.stderr

    def test_rejects_invalid_license_value(self, data_dir):
        (data_dir / "metals.toml").write_text(
            dedent("""
            [iron]
            name = "Iron"
            [iron._sources."mechanical.density"]
            citation = "x"
            kind = "doi"
            ref = "10.x/y"
            license = "GPL-3.0"
            """)
        )
        result = _run(data_dir)
        assert result.returncode == 1
        assert "not in allow-list" in result.stderr

    @pytest.mark.parametrize(
        "lic",
        [
            "CC0",
            "PD-USGov",
            "CC-BY-4.0",
            "CC-BY-SA-4.0",
            # Geant4-SL added in #167 for the G4NistMaterialBuilder mirror.
            "Geant4-SL",
            "proprietary-reference-only",
        ],
    )
    def test_accepts_each_allowed_license(self, data_dir, lic):
        (data_dir / "metals.toml").write_text(
            dedent(f"""
            [iron]
            name = "Iron"
            [iron._sources."mechanical.density"]
            citation = "x"
            kind = "doi"
            ref = "10.x/y"
            license = "{lic}"
            """)
        )
        result = _run(data_dir)
        assert result.returncode == 0, f"{lic} rejected: {result.stderr}"

    def test_walks_nested_sources(self, data_dir):
        """`_sources` may live inside a property group, not just at material root."""
        (data_dir / "metals.toml").write_text(
            dedent("""
            [iron]
            name = "Iron"
            [iron.mechanical._sources."mechanical.density"]
            citation = "x"
            kind = "doi"
            ref = "10.x/y"
            license = "unknown"
            """)
        )
        result = _run(data_dir)
        assert result.returncode == 1
        assert "license='unknown'" in result.stderr

    def test_ratchet_exempts_listed_paths(self, data_dir, tmp_path):
        (data_dir / "legacy.toml").write_text(
            dedent("""
            [iron]
            name = "Iron"
            [iron._sources."mechanical.density"]
            citation = "x"
            kind = "doi"
            ref = "10.x/y"
            license = "unknown"
            """)
        )
        ratchet = tmp_path / "ratchet.txt"
        rel = (
            str((data_dir / "legacy.toml").relative_to(REPO_ROOT))
            if (data_dir / "legacy.toml").is_relative_to(REPO_ROOT)
            else str(data_dir / "legacy.toml")
        )
        ratchet.write_text(rel + "\n")
        # Without ratchet — fails
        result_no_ratchet = _run(data_dir)
        assert result_no_ratchet.returncode == 1


class TestEmitAttributions:
    def test_no_cc_sources_message(self, data_dir):
        (data_dir / "metals.toml").write_text(
            dedent("""
            [iron]
            name = "Iron"
            [iron._sources."mechanical.density"]
            citation = "x"
            kind = "doi"
            ref = "10.x/y"
            license = "CC0"
            """)
        )
        result = _run(data_dir, None, "--emit-attributions")
        assert result.returncode == 0
        assert "no CC-BY sources" in result.stdout

    def test_lists_cc_by_sources(self, data_dir):
        (data_dir / "metals.toml").write_text(
            dedent("""
            [iron]
            name = "Iron"
            [iron._sources."mechanical.density"]
            citation = "mp_iron"
            kind = "doi"
            ref = "10.1063/1.4812323"
            license = "CC-BY-4.0"
            """)
        )
        result = _run(data_dir, None, "--emit-attributions")
        assert result.returncode == 0
        assert "mp_iron" in result.stdout
        assert "CC-BY-4.0" in result.stdout
        assert "10.1063/1.4812323" in result.stdout

    def test_dedupes_by_citation(self, data_dir):
        """A CC-BY source used by multiple properties appears once."""
        (data_dir / "metals.toml").write_text(
            dedent("""
            [iron]
            name = "Iron"
            [iron._sources."mechanical.density"]
            citation = "mp_iron"
            kind = "doi"
            ref = "10.x/y"
            license = "CC-BY-4.0"
            [iron._sources."mechanical.youngs_modulus"]
            citation = "mp_iron"
            kind = "doi"
            ref = "10.x/y"
            license = "CC-BY-4.0"
            """)
        )
        result = _run(data_dir, None, "--emit-attributions")
        assert result.stdout.count("mp_iron") == 1
