"""Tests for `scripts/_curation` — Phase 4 prep shared helpers.

Covers:
* `cached_get`: cache hit avoids second network call; TTL expiry refetches.
* `UnitNormalizer`: rejects unknown source/unit pairs; applies registered scale.
* `build_source_row`: rejects invalid `kind` and `license` values.
* `writeback`: round-trips a TOML preserving comments + formatting.
* `load_material_keys`: enumerates expected dotted paths from `metals.toml`.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from textwrap import dedent

import pytest

# scripts/ isn't on sys.path by default (it's not a package); inject it.
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import _curation  # noqa: E402
from _curation import (  # noqa: E402
    UnitNormalizer,
    build_source_row,
    cached_get,
    load_material_keys,
    writeback,
)

# --------------------------------------------------------------------------- #
# cached_get                                                                  #
# --------------------------------------------------------------------------- #


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def _redirect_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    cache_dir = tmp_path / "cache"
    monkeypatch.setattr(_curation, "CACHE_DIR", cache_dir)
    return cache_dir


def test_cached_get_uses_disk_on_second_call(monkeypatch, tmp_path):
    _redirect_cache(monkeypatch, tmp_path)
    calls = {"n": 0}

    def fake_get(url, params=None, headers=None, timeout=None):
        calls["n"] += 1
        return _FakeResponse({"hello": "world", "n": calls["n"]})

    monkeypatch.setattr(_curation.requests, "get", fake_get)

    out1 = cached_get("https://example.test/api", source="unit-test")
    out2 = cached_get("https://example.test/api", source="unit-test")

    assert calls["n"] == 1, "second call should hit the disk cache"
    assert out1 == out2 == {"hello": "world", "n": 1}


def test_cached_get_refetches_after_ttl_expiry(monkeypatch, tmp_path):
    cache_dir = _redirect_cache(monkeypatch, tmp_path)
    calls = {"n": 0}

    def fake_get(url, params=None, headers=None, timeout=None):
        calls["n"] += 1
        return _FakeResponse({"n": calls["n"]})

    monkeypatch.setattr(_curation.requests, "get", fake_get)

    cached_get("https://example.test/ttl", source="ttl-test", ttl_days=1)
    # Expire the cache file by backdating its mtime two days into the past.
    files = list((cache_dir / "ttl-test").glob("*.json"))
    assert len(files) == 1
    past = time.time() - 2 * 86400
    os.utime(files[0], (past, past))

    out2 = cached_get("https://example.test/ttl", source="ttl-test", ttl_days=1)
    assert calls["n"] == 2
    assert out2 == {"n": 2}


def test_cached_get_post_with_data(monkeypatch, tmp_path):
    _redirect_cache(monkeypatch, tmp_path)
    received = {}

    def fake_post(url, params=None, data=None, headers=None, timeout=None):
        received["data"] = data
        received["headers"] = headers
        return _FakeResponse({"ok": True})

    monkeypatch.setattr(_curation.requests, "post", fake_post)

    out = cached_get(
        "https://example.test/sparql",
        source="post-test",
        method="POST",
        data={"query": "SELECT *"},
    )
    assert out == {"ok": True}
    assert received["data"] == {"query": "SELECT *"}
    assert "pymat-curation" in received["headers"]["User-Agent"]


# --------------------------------------------------------------------------- #
# UnitNormalizer                                                              #
# --------------------------------------------------------------------------- #


def test_unit_normalizer_applies_registered_scale():
    n = UnitNormalizer()
    n.register("wikidata", "Q844211", "g/cm^3", scale=1e-3)
    value, unit = n.normalize("wikidata", 2700.0, "Q844211", target_property="density")
    assert unit == "g/cm^3"
    assert value == pytest.approx(2.7)


def test_unit_normalizer_passthrough_when_already_canonical():
    n = UnitNormalizer()
    n.register("wikidata", "Q13147228", "g/cm^3")
    value, unit = n.normalize("wikidata", 2.7, "Q13147228", target_property="density")
    assert unit == "g/cm^3"
    assert value == pytest.approx(2.7)


def test_unit_normalizer_rejects_unknown_source():
    n = UnitNormalizer()
    n.register("wikidata", "Q13147228", "g/cm^3")
    with pytest.raises(KeyError, match="source='nist_webbook'"):
        n.normalize("nist_webbook", 1.0, "g/cm**3", target_property="density")


def test_unit_normalizer_rejects_unknown_unit():
    n = UnitNormalizer()
    n.register("wikidata", "Q13147228", "g/cm^3")
    with pytest.raises(KeyError, match="unit='Q999999'"):
        n.normalize("wikidata", 1.0, "Q999999", target_property="density")


# --------------------------------------------------------------------------- #
# build_source_row                                                            #
# --------------------------------------------------------------------------- #


def test_build_source_row_happy_path():
    row = build_source_row(
        citation="Q663",
        kind="qid",
        ref="https://www.wikidata.org/wiki/Q663",
        license="CC0",
    )
    assert row == {
        "citation": "Q663",
        "kind": "qid",
        "ref": "https://www.wikidata.org/wiki/Q663",
        "license": "CC0",
    }


def test_build_source_row_includes_note():
    row = build_source_row(
        citation="10.1234/x", kind="doi", ref="doi:10.1234/x", license="CC-BY-4.0", note="page 42"
    )
    assert row["note"] == "page 42"


def test_build_source_row_rejects_invalid_kind():
    with pytest.raises(ValueError, match="kind="):
        build_source_row(citation="x", kind="blog", ref="x", license="CC0")


def test_build_source_row_rejects_invalid_license():
    with pytest.raises(ValueError, match="license="):
        build_source_row(citation="x", kind="doi", ref="x", license="GPL-3.0")


def test_build_source_row_rejects_unknown_license_alias():
    with pytest.raises(ValueError, match="license='unknown'"):
        build_source_row(citation="x", kind="doi", ref="x", license="unknown")


def test_build_source_row_requires_citation_and_ref():
    with pytest.raises(ValueError, match="citation"):
        build_source_row(citation="", kind="doi", ref="x", license="CC0")
    with pytest.raises(ValueError, match="ref"):
        build_source_row(citation="x", kind="doi", ref="", license="CC0")


# --------------------------------------------------------------------------- #
# writeback                                                                   #
# --------------------------------------------------------------------------- #


def test_writeback_preserves_comments_and_updates_value(tmp_path):
    src = dedent(
        """\
        # top-of-file comment — must survive the round-trip
        [aluminum]
        name = "Aluminum"

        [aluminum.al6061]
        # grade-level comment
        name = "Aluminum 6061-T6"
        grade = "6061-T6"

        [aluminum.al6061.mechanical]
        # density was rounded; replace with NIST value
        density_value = 2.70
        density_unit = "g/cm^3"
        """
    )
    p = tmp_path / "al.toml"
    p.write_text(src)

    modified = writeback(
        p,
        ["aluminum", "al6061", "mechanical"],
        {"density_value": 2.6989, "density_unit": "g/cm^3"},
    )
    assert modified is True

    out = p.read_text()
    assert "# top-of-file comment" in out
    assert "# grade-level comment" in out
    assert "# density was rounded" in out
    assert "density_value = 2.6989" in out


def test_writeback_attaches_sources_block(tmp_path):
    src = dedent(
        """\
        [aluminum]
        name = "Aluminum"

        [aluminum.al6061]
        name = "Aluminum 6061-T6"

        [aluminum.al6061.mechanical]
        density_value = 2.70
        density_unit = "g/cm^3"
        """
    )
    p = tmp_path / "al.toml"
    p.write_text(src)

    row = build_source_row(
        citation="Q663", kind="qid", ref="https://www.wikidata.org/wiki/Q663", license="CC0"
    )
    writeback(
        p,
        ["aluminum", "al6061", "mechanical"],
        {"density_value": 2.6989},
        sources={"density": row},
    )

    out = p.read_text()
    assert "[aluminum.al6061._sources]" in out
    assert "mechanical.density" in out
    assert "Q663" in out


def test_writeback_returns_false_when_unchanged(tmp_path):
    # Use an integer-valued float and a string so tomlkit's serialized
    # form is identical to the source — that's the contract `writeback`
    # promises ("True iff the file changed on disk").
    src = dedent(
        """\
        [aluminum]
        name = "Aluminum"

        [aluminum.mechanical]
        density_unit = "g/cm^3"
        """
    )
    p = tmp_path / "al.toml"
    p.write_text(src)

    modified = writeback(
        p,
        ["aluminum", "mechanical"],
        {"density_unit": "g/cm^3"},
    )
    assert modified is False


# --------------------------------------------------------------------------- #
# load_material_keys                                                          #
# --------------------------------------------------------------------------- #


def test_load_material_keys_finds_expected_metals():
    keys = load_material_keys("metals")
    # Family-level entries we know exist.
    assert "stainless" in keys
    assert "aluminum" in keys
    # At least one nested grade should appear.
    assert any(k.startswith("aluminum.") for k in keys)
    # Property-group sub-tables must NOT leak in as materials.
    assert "stainless.mechanical" not in keys
    assert "aluminum.thermal" not in keys


def test_load_material_keys_against_synthetic_toml(tmp_path):
    p = tmp_path / "synthetic.toml"
    p.write_text(
        dedent(
            """\
            [foo]
            name = "Foo"
            [foo.mechanical]
            density_value = 1.0
            [foo.bar]
            name = "Foo bar grade"
            [foo._sources]
            _default = {citation = "x", kind = "doi", ref = "x", license = "CC0"}
            [baz]
            name = "Baz"
            """
        )
    )
    keys = load_material_keys("synthetic", data_dir=tmp_path)
    assert keys == ["foo", "foo.bar", "baz"]


# --------------------------------------------------------------------------- #
# Wikidata enricher --dry-run integration                                     #
# --------------------------------------------------------------------------- #


def test_wikidata_dry_run_uses_fixture(monkeypatch, capsys):
    # Import lazily — the script lives at scripts/enrich_from_wikidata.py
    # and pulls in pymat at import time.
    import importlib

    enricher = importlib.import_module("enrich_from_wikidata")

    def boom(*a, **kw):  # pragma: no cover — must not be called
        raise AssertionError("network must not be hit in --dry-run")

    monkeypatch.setattr(enricher.requests, "post", boom)
    monkeypatch.setattr(enricher.requests, "get", boom)

    rc = enricher.compare(key_filter=None, dry_run=True)
    assert rc == 0
    captured = capsys.readouterr()
    assert "material" in captured.out
    assert "Wikidata values are CC0" in captured.out


def test_wikidata_fixture_file_is_valid_json():
    fixture = Path(__file__).parent / "fixtures" / "wikidata_sample.json"
    payload = json.loads(fixture.read_text())
    assert "results" in payload and "bindings" in payload["results"]
