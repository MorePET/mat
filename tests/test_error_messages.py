"""Pin the *content* of user-facing error messages.

Bernhard's mat-vis #280 / #286 are the canonical example of an error path
that fired correctly (line coverage 100%) but said useless things to the
user — internal UUIDs instead of the human name they typed, no
suggestions, no actionable guidance. This suite exists so a future
refactor can't silently regress error UX.

What we pin per error path:

1. **User-given input echoed**: the EXACT string the user typed appears
   in the message. Not normalized, not the resolved internal id.
2. **Close-match suggestions** where appropriate (mirror what
   ``pymat._lookup`` does today). Gaps are pinned as ``xfail`` —
   each xfail = a candidate issue to file.
3. **No internal-ID leakage** when the user supplied a human name.
4. **Error type stability** — the documented exception class doesn't
   silently change to something else under a "code cleanup".
5. **Empty / whitespace input** raises clearly, doesn't silently return
   the whole library or an empty list.

Pattern: ``pytest.raises(..., match=re.escape(user_input))``. Human
material names contain regex specials regularly — ``"Saint-Gobain"``,
``"AlOH3"``, ``"Co60"`` — so always escape.
"""

from __future__ import annotations

import re

import pytest

import pymat

# Public-error vocabulary: the set of exception class names a consumer
# may reasonably ``except`` for. If a refactor changes a documented
# error to something outside this set it should be a deliberate API
# bump, not a stealth rename.
_PUBLIC_ERROR_VOCAB = frozenset(
    {
        "KeyError",
        "ValueError",
        "TypeError",
        "AttributeError",
        "FileNotFoundError",
        "LookupError",  # parent of KeyError; tolerated
    }
)

# Sentinel-ish strings that internal-ID leakage tests should never see
# in a human-name miss. Internal keys ("s304", "s316L") and UUID-like
# tokens are the obvious tells.
_UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)


@pytest.fixture(autouse=True, scope="module")
def _load_all_categories():
    """Load the full library once per module so tests see real data.

    The repo's autouse ``clear_registry`` (function-scoped, in
    conftest.py) wipes the registry between tests, so we re-load here
    in a fixture that runs INSIDE the function-scoped clear. Net effect:
    every test starts with the full library loaded.
    """
    pymat.load_all()


@pytest.fixture(autouse=True)
def _reload_per_test():
    pymat.load_all()
    yield


# ── Helpers ───────────────────────────────────────────────────────


def _assert_input_echoed(msg: str, user_input: str) -> None:
    """The exact user-supplied string (or its ``repr``) must appear."""
    assert user_input in msg or repr(user_input) in msg, (
        f"user input {user_input!r} not echoed in error message:\n  {msg!r}"
    )


def _assert_no_uuid_leakage(msg: str) -> None:
    assert not _UUID_RE.search(msg), f"UUID leaked into human-name error message:\n  {msg!r}"


def _assert_error_class_public(exc: BaseException) -> None:
    name = type(exc).__name__
    assert name in _PUBLIC_ERROR_VOCAB, (
        f"{name} is not in the public-error vocabulary {_PUBLIC_ERROR_VOCAB}; "
        f"a documented error path should not raise {name}"
    )


# ────────────────────────────────────────────────────────────────────
# 1. pymat[name] — the gold-standard surface
# ────────────────────────────────────────────────────────────────────


class TestSubscriptInputEcho:
    """``pymat["..."]`` — already does the right thing. Pin it so we don't
    regress."""

    @pytest.mark.parametrize(
        "user_input",
        [
            "Portoro Green Marble",
            "Saint-Gobain LYSO:CeXYZ_unknown_variant",
            "AlOH3",
            "Co60",
            "Steel (annealed)",
            # Real punctuation from real pasted catalog entries
            "316/316L Dual-Cert",
        ],
    )
    def test_miss_echoes_exact_input(self, user_input: str):
        with pytest.raises(KeyError) as excinfo:
            _ = pymat[user_input]
        _assert_input_echoed(str(excinfo.value), user_input)
        _assert_error_class_public(excinfo.value)

    def test_miss_no_uuid_leakage(self):
        with pytest.raises(KeyError) as excinfo:
            _ = pymat["Portoro Green Marble"]
        _assert_no_uuid_leakage(str(excinfo.value))

    def test_typo_includes_close_matches(self):
        with pytest.raises(KeyError) as excinfo:
            _ = pymat["stainles stell 304"]
        msg = str(excinfo.value)
        _assert_input_echoed(msg, "stainles stell 304")
        # The gold-standard error mentions "Close matches:".
        assert "Close matches" in msg or "stainless" in msg.lower(), (
            f"typo error must offer close matches; got: {msg!r}"
        )

    def test_ambiguous_lists_candidates(self):
        from pymat import Material, registry

        m1 = Material(name="Duplicate Surface Name")
        m2 = Material(name="Duplicate Surface Name")
        try:
            registry.register("dupe_a", m1)
            registry.register("dupe_b", m2)
            with pytest.raises(KeyError) as excinfo:
                _ = pymat["Duplicate Surface Name"]
            msg = str(excinfo.value)
            _assert_input_echoed(msg, "Duplicate Surface Name")
            assert "Ambiguous" in msg or "match" in msg
        finally:
            registry._REGISTRY.pop("dupe_a", None)
            registry._REGISTRY.pop("dupe_b", None)


class TestSubscriptEmptyAndType:
    """Already pinned in test_lookup; mirror here so this file is a
    self-contained pin. Plus add a few we DON'T pin elsewhere."""

    @pytest.mark.parametrize("bad", ["", "   ", "\t\n  "])
    def test_empty_or_whitespace_raises_clearly(self, bad: str):
        with pytest.raises(KeyError, match="non-empty"):
            _ = pymat[bad]

    def test_non_string_says_what_it_got(self):
        with pytest.raises(TypeError) as excinfo:
            _ = pymat[42]
        msg = str(excinfo.value)
        # Should mention the offending type
        assert "int" in msg, f"TypeError must name the bad type; got: {msg!r}"


# ────────────────────────────────────────────────────────────────────
# 2. pymat.search — empty, no-results
# ────────────────────────────────────────────────────────────────────


class TestSearchInputContract:
    """``pymat.search`` returns ``[]`` for empty / whitespace queries by
    docstring contract. That's a soft contract — pinning it here so a
    "be helpful" refactor doesn't decide to surface the entire library
    on empty input.
    """

    @pytest.mark.parametrize("bad", ["", "   ", "\t\n"])
    def test_empty_search_returns_empty_list(self, bad: str):
        # Contract: empty/whitespace query → empty list. Not the full
        # library. Not an error. (See _normalize in search.py.)
        assert pymat.search(bad) == []
        assert pymat.search(bad, exact=True) == []

    @pytest.mark.xfail(
        reason=(
            "search('totallybogus_xyz_12345') currently returns several lyso "
            "materials because the rapidfuzz partial_ratio threshold "
            "misfires on long underscore-separated tokens. There is no error "
            "channel for 'no results would be more honest than these results' "
            "today. Candidate issue: tighten the threshold or surface a "
            "warning when total score is way below the top genuine hit."
        ),
        strict=False,
    )
    def test_truly_unrelated_query_returns_empty(self):
        # A long, clearly-bogus query should not match real materials.
        # Currently does — see xfail reason.
        assert pymat.search("zzzzz_yyyyy_xxxxx_wwwww_unrelated") == []


# ────────────────────────────────────────────────────────────────────
# 3. pymat.<attr> — module-level lazy attribute access
# ────────────────────────────────────────────────────────────────────


class TestModuleAttributeMiss:
    def test_unknown_material_attr_lists_available(self):
        with pytest.raises(AttributeError) as excinfo:
            _ = pymat.totally_not_a_real_material
        msg = str(excinfo.value)
        _assert_input_echoed(msg, "totally_not_a_real_material")
        # Already lists "Available materials" today
        assert "Available" in msg, f"attribute miss should list available; got: {msg!r}"

    @pytest.mark.xfail(
        reason=(
            "pymat.<typo> uses an exact-list-of-bases lookup with no fuzzy "
            "fallback — `pymat.stinless` is a hard miss with no 'did you "
            "mean stainless?' hint. Candidate issue: route attribute miss "
            "through the same fuzzy-suggest helper as _lookup."
        ),
        strict=False,
    )
    def test_module_attr_typo_offers_suggestion(self):
        with pytest.raises(AttributeError) as excinfo:
            _ = pymat.stinless
        msg = str(excinfo.value)
        # Today's behavior: just lists every base. We want the close
        # match (stainless) called out.
        assert "stainless" in msg.lower() and (
            "did you mean" in msg.lower() or "close" in msg.lower() or "suggest" in msg.lower()
        )


# ────────────────────────────────────────────────────────────────────
# 4. Material.<child> — variant access on a Material
# ────────────────────────────────────────────────────────────────────


class TestMaterialVariantMiss:
    def test_missing_variant_echoes_parent_name_and_input(self):
        with pytest.raises(AttributeError) as excinfo:
            _ = pymat.stainless.totally_not_a_grade
        msg = str(excinfo.value)
        _assert_input_echoed(msg, "totally_not_a_grade")
        # Parent identity should be in the message so user knows where
        # they were looking
        assert "Stainless Steel" in msg or "stainless" in msg.lower()
        # Message lists existing variants
        assert "Available" in msg

    @pytest.mark.xfail(
        reason=(
            "Material.__getattr__ lists all available variants verbatim but "
            "doesn't offer a 'did you mean s304?' for typos like "
            "stainless.s30 (intent: s304). Candidate issue: fuzzy-suggest "
            "the closest available child."
        ),
        strict=False,
    )
    def test_variant_typo_offers_close_suggestion(self):
        with pytest.raises(AttributeError) as excinfo:
            _ = pymat.stainless.s30  # typo for s304
        msg = str(excinfo.value).lower()
        assert "did you mean" in msg or "close" in msg or "suggest" in msg


# ────────────────────────────────────────────────────────────────────
# 5. load_category — load-time errors
# ────────────────────────────────────────────────────────────────────


class TestLoadCategoryMiss:
    def test_unknown_category_echoes_input(self):
        with pytest.raises(FileNotFoundError) as excinfo:
            pymat.load_category("totally_made_up_category")
        msg = str(excinfo.value)
        _assert_input_echoed(msg, "totally_made_up_category")
        _assert_error_class_public(excinfo.value)

    @pytest.mark.xfail(
        reason=(
            "load_category('totally_made_up_category') raises "
            "FileNotFoundError with the resolved filesystem path but does "
            "NOT list available categories or suggest the closest match. "
            "Candidate issue: enumerate categories in the error and offer "
            "fuzzy suggestion."
        ),
        strict=False,
    )
    def test_unknown_category_lists_available(self):
        with pytest.raises(FileNotFoundError) as excinfo:
            pymat.load_category("metls")  # typo for metals
        msg = str(excinfo.value).lower()
        assert "metals" in msg and ("available" in msg or "did you mean" in msg or "close" in msg)


# ────────────────────────────────────────────────────────────────────
# 6. Vis.finish setter
# ────────────────────────────────────────────────────────────────────


class TestVisFinishUnknown:
    def test_unknown_finish_lists_available(self):
        v = pymat.stainless.vis
        available = list(v.finishes.keys())
        assert available, "fixture sanity: stainless must have finishes"

        with pytest.raises(ValueError) as excinfo:
            v.finish = "shiny_nonexistent"
        msg = str(excinfo.value)
        _assert_input_echoed(msg, "shiny_nonexistent")
        for finish_name in available:
            assert finish_name in msg, (
                f"available finish {finish_name!r} missing from error: {msg!r}"
            )

    def test_unknown_finish_error_type_is_valueerror(self):
        v = pymat.stainless.vis
        with pytest.raises(ValueError) as excinfo:
            v.finish = "bogus"
        _assert_error_class_public(excinfo.value)


# ────────────────────────────────────────────────────────────────────
# 7. Vis.tier setter
# ────────────────────────────────────────────────────────────────────


class TestVisTierUnknown:
    """Tier validation is the symmetric case to finish validation. Today,
    ``vis.tier = "bogus"`` succeeds silently — the bad tier reaches
    mat-vis-client at fetch time, where it surfaces a less-targeted
    error. This is exactly the class of bug Bernhard hit (#280): the
    error fires at the wrong layer with the wrong context.
    """

    def test_unknown_tier_raises_with_input_echoed(self):
        """``Vis.tier = 'bogus'`` raises ``ValueError`` with the input
        echoed and the available tiers listed — mirrors the
        ``Vis.finish`` pattern. Closes the asymmetry between the two
        identity setters and the at-wrong-layer / no-input-echo class
        of bug Bernhard hit in mat-vis #280."""
        v = pymat.stainless.vis
        with pytest.raises(ValueError) as excinfo:
            v.tier = "definitely_not_a_real_tier"
        msg = str(excinfo.value)
        _assert_input_echoed(msg, "definitely_not_a_real_tier")
        # The available tiers must be listed — a consumer needs the
        # actual options, not just "tier" in the error text.
        assert "1k" in msg, f"available-tiers list missing from error: {msg!r}"


# ────────────────────────────────────────────────────────────────────
# 8. Vis.override unknown kwargs (typo guard)
# ────────────────────────────────────────────────────────────────────


class TestVisOverrideUnknownKwarg:
    def test_typo_kwarg_echoes_typo_and_lists_valid(self):
        v = pymat.stainless.vis
        with pytest.raises(TypeError) as excinfo:
            v.override(roughnes=0.5)  # typo for roughness
        msg = str(excinfo.value)
        # Pin: the actual typo'd kwarg name appears verbatim
        _assert_input_echoed(msg, "roughnes")
        # Pin: valid kwargs are listed so the user can correct
        assert "roughness" in msg, f"valid keys must include roughness: {msg!r}"


# ────────────────────────────────────────────────────────────────────
# 9. Vis.from_toml malformed entries
# ────────────────────────────────────────────────────────────────────


class TestVisFromTomlMalformed:
    def test_slashed_string_form_echoes_value(self):
        from pymat.vis._model import Vis

        with pytest.raises(ValueError) as excinfo:
            Vis.from_toml({"finishes": {"brushed": "ambientcg/Metal032"}})
        msg = str(excinfo.value)
        # Pin: bad value AND finish name both echoed
        assert "brushed" in msg
        _assert_input_echoed(msg, "ambientcg/Metal032")

    def test_malformed_inline_table_echoes_finish_name(self):
        from pymat.vis._model import Vis

        with pytest.raises(ValueError) as excinfo:
            Vis.from_toml({"finishes": {"shiny": {"source": "x"}}})  # missing id
        msg = str(excinfo.value)
        assert "shiny" in msg
        # Documented expectation: explain what was expected
        assert "source" in msg and "id" in msg


# ────────────────────────────────────────────────────────────────────
# 10. source_id read-only setter
# ────────────────────────────────────────────────────────────────────


class TestSourceIdReadOnly:
    def test_setter_raises_attribute_error_with_guidance(self):
        v = pymat.stainless.vis
        with pytest.raises(AttributeError) as excinfo:
            v.source_id = "polyhaven/Metal999"
        msg = str(excinfo.value)
        _assert_error_class_public(excinfo.value)
        # The error must guide the user to the replacement API
        assert "source" in msg and "material_id" in msg, (
            f"read-only error must point at the replacement API: {msg!r}"
        )


# ────────────────────────────────────────────────────────────────────
# 11. Material.with_vis bad input
# ────────────────────────────────────────────────────────────────────


class TestMaterialWithVisBadArg:
    def test_non_vis_arg_says_what_it_got(self):
        from pymat import Material

        m = Material(name="probe")
        with pytest.raises(TypeError) as excinfo:
            m.with_vis("not a Vis")
        msg = str(excinfo.value)
        # Pin: error names the actual offending type
        assert "str" in msg, f"with_vis error must name the bad type: {msg!r}"
        _assert_error_class_public(excinfo.value)


# ────────────────────────────────────────────────────────────────────
# 12. Material.apply_to wrong target
# ────────────────────────────────────────────────────────────────────


class TestApplyToBadTarget:
    def test_immutable_target_says_what_it_got(self):
        m = pymat.stainless
        with pytest.raises(TypeError) as excinfo:
            m.apply_to(42)
        msg = str(excinfo.value)
        assert "int" in msg, f"apply_to error must name the bad type: {msg!r}"
        _assert_error_class_public(excinfo.value)


# ────────────────────────────────────────────────────────────────────
# 13. Adapter contract on a Material with no vis mapping
# ────────────────────────────────────────────────────────────────────


class TestAdapterNoMapping:
    """``to_threejs(Material(name="X"))`` — what does it do?

    Today: it returns a default-PBR dict (grey 0.5 roughness, 0 metallic
    etc.) and never raises. Documented: ``has_mapping`` False → empty
    textures dict. So a custom material with no Vis mapping silently
    renders as default grey.

    Pin the silent-success contract today, and xfail the "should warn
    or raise" preference. If we ever decide to make this loud, the xfail
    flips to a real assertion.
    """

    def test_no_mapping_to_threejs_returns_dict_silently(self):
        from pymat import Material
        from pymat import vis as vis_mod

        m = Material(name="Bare Custom")
        result = vis_mod.to_threejs(m)
        # Pin the documented behavior: returns a usable dict, no raise.
        assert isinstance(result, dict)
        assert result.get("type") == "MeshPhysicalMaterial"

    def test_no_mapping_to_gltf_includes_material_name(self):
        """The user supplied a Material name — it must round-trip into
        the glTF output's ``name`` field. (The user's name is the most
        load-bearing piece of identity for an asset that fails to fetch
        textures: it's how they'll find which call site set up the
        material.)
        """
        from pymat import Material
        from pymat import vis as vis_mod

        m = Material(name="MyAlloyXYZ")
        result = vis_mod.to_gltf(m)
        assert result.get("name") == "MyAlloyXYZ"

    @pytest.mark.xfail(
        reason=(
            "to_threejs / to_gltf on a Material without a Vis mapping "
            "silently return default-PBR scalars (grey, roughness 0.5). "
            "This is the same UX failure mode as mat-vis #280: a downstream "
            "consumer ends up with an unexpected output and no breadcrumb "
            "back to the call site that failed to set up vis. Candidate "
            "issue: emit a warning (or raise on a strict=True flag) when "
            "the adapter receives a Material whose vis.has_mapping is "
            "False, with the Material.name echoed."
        ),
        strict=False,
    )
    def test_no_mapping_should_warn_or_raise(self):
        import warnings

        from pymat import Material
        from pymat import vis as vis_mod

        m = Material(name="MyBareAlloy")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            vis_mod.to_threejs(m)
        # Either a warning is emitted (preferred) or it raises (also
        # acceptable). Today neither happens.
        assert any("MyBareAlloy" in str(w.message) for w in caught), (
            "adapter on no-mapping Material must signal the silent default"
        )


# ────────────────────────────────────────────────────────────────────
# 14. Vis.fetch / textures error envelope (Bernhard's #280 case)
# ────────────────────────────────────────────────────────────────────


class TestFetchErrorEnvelope:
    """Reach-down into a real ``Vis.textures`` access on a bad mapping.

    We patch the underlying mat-vis-client to RAISE the kind of error
    Bernhard saw (a UUID-laden ``MaterialNotStagedError``). The contract
    we want from py-mat: it should NOT swallow that error AND it should
    add the human name (``Material.name``) so the user can find the call
    site even if mat-vis-client's message is opaque.

    Today: py-mat just bubbles. xfail the wrap.
    """

    @pytest.mark.xfail(
        reason=(
            "When mat-vis-client raises (e.g. MaterialNotStagedError) on "
            "Vis.textures access, py-mat doesn't wrap or annotate the "
            "exception with the owning Material.name or the user-supplied "
            "vis identity. Bernhard (mat-vis #280) had to read a UUID-only "
            "traceback to figure out WHICH material in his scene failed. "
            "Candidate issue: catch the client error in Vis._fetch and "
            "re-raise with Material.name + (source, material_id, tier) "
            "appended, so the user can find their call site."
        ),
        strict=False,
    )
    def test_fetch_failure_is_annotated_with_user_context(self, monkeypatch):
        import mat_vis_client as _client_mod

        from pymat import Material

        class FailingClient:
            def fetch_all_textures(self, source, material_id, *, tier="1k"):
                # Mimic mat-vis-client's MaterialNotStagedError shape:
                # UUID + tier, NO user-given name.
                raise RuntimeError(
                    f"material '34f2c1f9-6169-4975-b5d8-4e21f49ddf55' "
                    f"exists in '{source}' index but is not staged for "
                    f"tier '{tier}'. Needs a re-bake."
                )

            def channels(self, *args, **kwargs):
                return ["color"]

        monkeypatch.setattr(_client_mod, "_client", FailingClient())

        m = Material(
            name="MySpecificCarPaint",
            vis={"source": "gpuopen", "material_id": "MySpecificCarPaint"},
        )

        with pytest.raises(Exception) as excinfo:
            _ = m.vis.textures
        msg = str(excinfo.value)
        # The user's Material.name should be in the error chain
        # somewhere — that's the missing piece in #280.
        assert "MySpecificCarPaint" in msg, (
            "fetch failure must echo the human-given name; "
            "mat-vis-client's UUID-only message is exactly the #280 bug"
        )


# ────────────────────────────────────────────────────────────────────
# 15. pymat-mcp _not_found envelope (skipped if package not installed)
# ────────────────────────────────────────────────────────────────────


class TestMcpNotFoundEnvelope:
    """The MCP tool layer wraps misses in a ``did_you_mean`` envelope.
    We pin the envelope shape AND the input echo for that surface too.
    Skipped if pymat-mcp isn't installed in the test env.
    """

    @pytest.fixture(autouse=True)
    def _require_mcp(self):
        pytest.importorskip("pymat_mcp.tools")

    def test_get_material_miss_echoes_input(self):
        from pymat_mcp.tools import get_material

        result = get_material("Portoro Green Marble")
        assert "error" in result
        _assert_input_echoed(result["error"], "Portoro Green Marble")

    def test_get_material_miss_includes_did_you_mean_envelope(self):
        from pymat_mcp.tools import get_material

        result = get_material("Stinless 304")  # typo
        assert "did_you_mean" in result, "MCP miss envelope must include did_you_mean key"
        # Each suggestion is a {key, name} pair (per docstring contract)
        for s in result["did_you_mean"]:
            assert "key" in s and "name" in s

    def test_get_material_miss_no_uuid_leakage(self):
        from pymat_mcp.tools import get_material

        result = get_material("Portoro Green Marble")
        msg = result["error"]
        _assert_no_uuid_leakage(msg)
