"""Tests for pure tool functions (no MCP runtime).

Each tool returns a JSON-serializable dict. Tests pin the output
shape (so future agents reading tool descriptions don't get
surprised by a schema change) plus golden-material round-trips
(so a refactor that breaks lookups goes red on this side, not in
agent traces).
"""

from __future__ import annotations

import json

import pytest
from pymat_mcp import tools

# ── search_materials ──────────────────────────────────────────


class TestSearchMaterials:
    def test_returns_query_and_results_keys(self):
        out = tools.search_materials("stainless")
        assert set(out.keys()) == {"query", "results"}
        assert out["query"] == "stainless"

    def test_results_are_brief_rows(self):
        out = tools.search_materials("Stainless Steel 304")
        assert out["results"], "no hits for known material"
        row = out["results"][0]
        assert set(row.keys()) >= {"key", "name", "grade", "category", "density"}

    def test_limit_respected(self):
        out = tools.search_materials("steel", limit=2)
        assert len(out["results"]) <= 2

    def test_unknown_query_returns_empty_list(self):
        out = tools.search_materials("xyzzy_no_such_material")
        assert out["results"] == []

    def test_serializable(self):
        """Tool output must round-trip through JSON — agents see this
        as a tool response."""
        out = tools.search_materials("aluminum")
        json.dumps(out)  # raises if not serializable


# ── get_material ──────────────────────────────────────────────


class TestGetMaterial:
    def test_full_dump_for_known_material(self):
        out = tools.get_material("Stainless Steel 304")
        assert "error" not in out
        assert out["name"] == "Stainless Steel 304"
        assert out["grade"] == "304"
        assert "properties" in out
        assert "mechanical" in out["properties"]
        assert out["properties"]["mechanical"]["density"] == 8.0
        assert "vis" in out
        assert out["vis"]["source"] == "ambientcg"

    def test_lookup_by_grade(self):
        """``304`` alone resolves via the grade-aware lookup."""
        out = tools.get_material("304")
        assert "error" not in out
        assert out["grade"] == "304"

    def test_unknown_returns_error_with_suggestions(self):
        # Mild typo / partial — close enough for the fuzzy matcher to
        # surface stainless candidates.
        out = tools.get_material("Stainless 304")
        if "error" in out:
            assert "did_you_mean" in out
            # Suggestions are now {key, name} pairs so the agent can
            # retry with the canonical key, not just the human name.
            for s in out["did_you_mean"]:
                assert "key" in s and "name" in s
            assert any("stainless" in s["name"].lower() for s in out["did_you_mean"])
        else:
            assert "stainless" in out["name"].lower()

    def test_unknown_returns_error_envelope_for_garbage(self):
        """Hard-miss → error envelope; suggestion list may be empty."""
        out = tools.get_material("xyzzy_not_a_real_material_anywhere")
        assert "error" in out
        assert "did_you_mean" in out  # key present, list may be empty
        # Even with no matches, every entry would be a {key, name} pair
        for s in out["did_you_mean"]:
            assert set(s.keys()) >= {"key", "name"}

    def test_domains_filter_narrows_payload(self):
        full = tools.get_material("Stainless Steel 304")
        narrow = tools.get_material("Stainless Steel 304", domains=["mechanical"])
        assert set(full["properties"].keys()) > set(narrow["properties"].keys())
        assert list(narrow["properties"].keys()) == ["mechanical"]

    def test_unknown_domain_silently_dropped(self):
        """Typos in ``domains`` shouldn't error — just return what's
        valid. Matches the kwargs forgiveness pattern."""
        out = tools.get_material(
            "Stainless Steel 304",
            domains=["mechanical", "not_a_real_domain"],
        )
        assert "error" not in out
        assert "mechanical" in out["properties"]

    def test_include_vis_false_omits_block(self):
        out = tools.get_material("Stainless Steel 304", include_vis=False)
        assert "vis" not in out
        # Properties still there
        assert "properties" in out

    def test_include_vis_default_true(self):
        out = tools.get_material("Stainless Steel 304")
        assert "vis" in out

    def test_serializable(self):
        out = tools.get_material("Stainless Steel 304")
        json.dumps(out)

    def test_property_dump_skips_none_values(self):
        """Compact payload — only set values appear."""
        out = tools.get_material("Stainless Steel 304")
        for group in out["properties"].values():
            for v in group.values():
                assert v is not None


# ── list_categories ───────────────────────────────────────────


class TestListCategories:
    def test_returns_list(self):
        out = tools.list_categories()
        assert "categories" in out
        assert isinstance(out["categories"], list)
        assert len(out["categories"]) >= 5  # we ship plenty of categories

    def test_includes_known_categories(self):
        out = tools.list_categories()
        cats = set(out["categories"])
        # Smoke: at least these top-level groups should be registered
        assert {"stainless", "aluminum"} & cats, (
            f"expected at least one of stainless/aluminum, got: {cats}"
        )

    def test_works_as_first_tool_call(self, tmp_path):
        """``list_categories`` must work in a fresh process where
        nothing has primed the registry yet. Earlier tests in the
        same session would silently mask a broken lazy-load by
        leaving categories already-loaded. Spawn a clean subprocess
        to pin the cold-start contract.
        """
        import json
        import subprocess
        import sys

        script = tmp_path / "probe.py"
        script.write_text(
            "import json\n"
            "from pymat_mcp import tools\n"
            "out = tools.list_categories()\n"
            "print(json.dumps(out))\n"
        )
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            check=True,
        )
        out = json.loads(result.stdout)
        assert out["categories"], (
            "list_categories returned [] in a cold-start process — "
            "lazy-load trigger is broken"
        )
        # And the known top-level categories should appear
        assert "stainless" in out["categories"]
        assert "aluminum" in out["categories"]


# ── list_grades ───────────────────────────────────────────────


class TestListGrades:
    def test_known_parent_returns_children(self):
        out = tools.list_grades("stainless")
        assert "error" not in out
        assert out["parent"]["name"].lower().startswith("stainless")
        assert len(out["children"]) > 0

    def test_unknown_parent_errors(self):
        out = tools.list_grades("not_a_real_category")
        assert "error" in out

    def test_leaf_node_has_empty_children(self):
        """A grade-level material shouldn't necessarily have children."""
        out = tools.list_grades("Stainless Steel 304")
        # Could be empty if no treatments are registered for s304;
        # the test just pins that it doesn't error.
        assert "error" not in out
        assert "children" in out


class TestListFinishes:
    def test_known_material_returns_finishes(self):
        out = tools.list_finishes("Stainless Steel 304")
        assert "error" not in out
        assert "default_finish" in out
        assert isinstance(out["finishes"], list)
        # s304 ships with at least one finish
        assert len(out["finishes"]) > 0
        for finish in out["finishes"]:
            assert set(finish.keys()) >= {"name", "source", "material_id"}

    def test_unknown_material_errors_with_suggestions(self):
        out = tools.list_finishes("not_real")
        assert "error" in out
        assert "did_you_mean" in out


# ── compute_mass ──────────────────────────────────────────────


class TestComputeMass:
    def test_known_density_returns_mass(self):
        out = tools.compute_mass("Stainless Steel 304", 1000.0)
        # 1000 mm³ × 8.0 g/cm³ = 1000 × 0.008 g/mm³ = 8.0 g
        assert abs(out["mass_g"] - 8.0) < 0.01
        assert out["density_g_per_cm3"] == 8.0
        assert out["volume_mm3"] == 1000.0

    def test_zero_volume_zero_mass(self):
        out = tools.compute_mass("Stainless Steel 304", 0.0)
        assert out["mass_g"] == 0.0

    def test_unknown_material_errors(self):
        out = tools.compute_mass("not_real", 100.0)
        assert "error" in out


# ── get_appearance ────────────────────────────────────────────


class TestGetAppearance:
    def test_returns_vis_dict(self):
        out = tools.get_appearance("Stainless Steel 304")
        assert "vis" in out
        v = out["vis"]
        assert v["source"] == "ambientcg"
        assert v["material_id"] is not None
        assert v["tier"] == "1k"
        assert isinstance(v["finishes"], dict)

    def test_unknown_errors(self):
        out = tools.get_appearance("not_real")
        assert "error" in out


# ── to_threejs / to_gltf ──────────────────────────────────────


class TestAdapterTools:
    def test_to_threejs_returns_dict(self):
        out = tools.to_threejs("Stainless Steel 304")
        assert "threejs" in out
        d = out["threejs"]
        # Three.js MeshPhysicalMaterial fields
        assert d["roughness"] is not None
        assert d["metalness"] is not None

    def test_to_gltf_returns_dict(self):
        out = tools.to_gltf("Stainless Steel 304")
        assert "gltf" in out
        # glTF material node has pbrMetallicRoughness
        assert "pbrMetallicRoughness" in out["gltf"]

    def test_finish_param_changes_output(self):
        """Passing ``finish="polished"`` should derive a variant with
        a different material_id (different texture identity) — proves
        the override+with_vis path is wired correctly."""
        base = tools.to_threejs("Stainless Steel 304")  # no finish
        polished = tools.to_threejs("Stainless Steel 304", finish="polished")
        # Exact asserts depend on TOML data; just check at least one
        # value differs (proves override fired).
        assert base["threejs"] != polished["threejs"]

    def test_finish_does_not_mutate_registry(self):
        """The to_threejs(finish=...) path must NOT corrupt the
        registry singleton. Pin it here; this is the load-bearing
        guarantee of the whole 3.6/3.7/3.8 hazard work."""
        import pymat

        steel = pymat["Stainless Steel 304"]
        original_mid = steel.vis.material_id

        tools.to_threejs("Stainless Steel 304", finish="polished")

        assert steel.vis.material_id == original_mid

    def test_unknown_material_errors(self):
        out = tools.to_threejs("not_real")
        assert "error" in out


# ── compare_materials ─────────────────────────────────────────


class TestCompareMaterials:
    def test_default_properties_returned(self):
        out = tools.compare_materials(["Stainless Steel 304", "Aluminum 6061"])
        assert "rows" in out
        assert len(out["rows"]) == 2
        # Default property set includes density
        assert "mechanical.density" in out["properties"]

    def test_custom_property_paths(self):
        out = tools.compare_materials(
            ["Stainless Steel 304"],
            properties=["mechanical.density", "thermal.melting_point"],
        )
        row = out["rows"][0]
        assert "mechanical.density" in row
        assert row["mechanical.density"] == 8.0

    def test_unknown_material_marked_in_row(self):
        out = tools.compare_materials(["not_a_real_key"])
        row = out["rows"][0]
        assert "error" in row

    def test_mixed_known_and_unknown(self):
        out = tools.compare_materials(["Stainless Steel 304", "not_real"])
        assert len(out["rows"]) == 2
        assert "error" not in out["rows"][0]
        assert "error" in out["rows"][1]


# ── JSON-serialization smoke across all tools ─────────────────


@pytest.mark.parametrize(
    "tool_call",
    [
        ("search_materials", ["stainless"], {}),
        ("get_material", ["Stainless Steel 304"], {}),
        ("list_categories", [], {}),
        ("list_grades", ["stainless"], {}),
        ("list_finishes", ["Stainless Steel 304"], {}),
        ("compute_mass", ["Stainless Steel 304", 100.0], {}),
        ("get_appearance", ["Stainless Steel 304"], {}),
        ("to_threejs", ["Stainless Steel 304"], {}),
        ("to_gltf", ["Stainless Steel 304"], {}),
        ("compare_materials", [["Stainless Steel 304"]], {}),
    ],
)
def test_every_tool_output_is_json_serializable(tool_call):
    """Every tool returns something JSON-serializable. Catches the
    moment any tool grows a ``bytes`` / ``Path`` / dataclass leak."""
    name, args, kwargs = tool_call
    fn = getattr(tools, name)
    out = fn(*args, **kwargs)
    json.dumps(out)
