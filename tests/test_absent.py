"""Tests for #243 — `_absent`, declared absences.

Per ADR-0004 §6: `None` on a property cannot distinguish "nobody looked" from
"we looked and the number does not exist". Those two facts should make a
downstream engine behave differently, so the second one gets recorded.
"""

from __future__ import annotations

from textwrap import dedent

import pytest

import pymat
from pymat.loader import load_toml
from pymat.sources import ABSENT_REASONS, Absent, parse_absent_table


class TestAbsentDataclass:
    def test_requires_a_reason(self):
        with pytest.raises(ValueError, match="missing required key 'reason'"):
            Absent.from_toml("optical.x", {"note": "hi"})

    def test_rejects_an_unknown_reason(self):
        with pytest.raises(ValueError, match="unknown reason"):
            Absent.from_toml("optical.x", {"reason": "lazy"})

    def test_error_lists_the_allowed_reasons(self):
        with pytest.raises(ValueError, match="not-separable"):
            Absent.from_toml("optical.x", {"reason": "lazy"})

    def test_reason_vocabulary_is_closed(self):
        """Free text cannot be counted, and the point of a declared absence is
        that it can be audited."""
        assert ABSENT_REASONS == {
            "not-measured",
            "not-applicable",
            "not-separable",
            "proprietary",
            "pending",
        }

    def test_note_is_optional(self):
        a = Absent.from_toml("optical.x", {"reason": "pending"})
        assert a.reason == "pending"
        assert a.note is None

    def test_non_table_entry_raises(self):
        with pytest.raises(ValueError, match="must be an inline table"):
            parse_absent_table({"optical.x": "nope"})


class TestAbsentLoading:
    def _load(self, tmp_path, body):
        p = tmp_path / "m.toml"
        p.write_text(dedent(body))
        return load_toml(p)

    def test_absent_is_parsed_and_queryable(self, tmp_path):
        mats = self._load(
            tmp_path,
            """
            [x]
            name = "X"
            [x._absent]
            "optical.reemit_qe" = { reason = "not-measured", note = "searched, nothing" }
            """,
        )
        a = mats["x"].absent("optical.reemit_qe")
        assert a.reason == "not-measured"
        assert a.note == "searched, nothing"
        assert mats["x"].is_absent("optical.reemit_qe")

    def test_unset_property_without_declaration_is_not_absent(self):
        """The distinction the whole mechanism exists to draw."""
        assert pymat.lyso.properties.optical.scattering_length is None
        assert not pymat.lyso.is_absent("optical.scattering_length")

    def test_bad_absent_table_raises_at_load(self, tmp_path):
        with pytest.raises(ValueError, match="_absent must be a TOML table"):
            self._load(
                tmp_path,
                """
                [x]
                name = "X"
                _absent = "nope"
                """,
            )

    def test_bad_reason_raises_at_load(self, tmp_path):
        with pytest.raises(ValueError, match="unknown reason"):
            self._load(
                tmp_path,
                """
                [x]
                name = "X"
                [x._absent]
                "optical.x" = { reason = "shrug" }
                """,
            )

    def test_absent_does_not_leak_into_properties(self, tmp_path):
        mats = self._load(
            tmp_path,
            """
            [x]
            name = "X"
            [x._absent]
            "optical.reemit_qe" = { reason = "not-measured" }
            """,
        )
        assert mats["x"].properties.optical.reemit_qe is None


class TestAbsentInheritance:
    def _load(self, tmp_path, body):
        p = tmp_path / "m.toml"
        p.write_text(dedent(body))
        return load_toml(p)

    def test_children_inherit_parent_absences(self, tmp_path):
        mats = self._load(
            tmp_path,
            """
            [x]
            name = "X"
            [x._absent]
            "optical.reemit_qe" = { reason = "not-measured" }
            [x.child]
            name = "Child"
            """,
        )
        assert mats["x"]._children["child"].is_absent("optical.reemit_qe")

    def test_child_can_override_the_reason(self, tmp_path):
        mats = self._load(
            tmp_path,
            """
            [x]
            name = "X"
            [x._absent]
            "optical.reemit_qe" = { reason = "not-measured" }
            [x.child]
            name = "Child"
            [x.child._absent]
            "optical.reemit_qe" = { reason = "proprietary" }
            """,
        )
        assert mats["x"].absent("optical.reemit_qe").reason == "not-measured"
        assert mats["x"]._children["child"].absent("optical.reemit_qe").reason == "proprietary"

    def test_a_child_that_has_the_measurement_just_sets_it(self, tmp_path):
        """The declared absence stays inherited, but the value is now real —
        so a consumer must check the value first, absence second."""
        mats = self._load(
            tmp_path,
            """
            [x]
            name = "X"
            [x._absent]
            "optical.reemit_qe" = { reason = "not-measured" }
            [x.child]
            name = "Child"
            [x.child.optical]
            reemit_qe = 0.75
            """,
        )
        child = mats["x"]._children["child"]
        assert child.properties.optical.reemit_qe == 0.75


class TestAbsentAPI:
    def test_short_alias_resolves(self):
        """`absent()` accepts the same short aliases as `source_of()`."""
        assert pymat.lyso.absent("decay_components") is not None
        assert pymat.lyso.absent("optical.decay_components") is not None

    def test_no_default_fallback(self):
        """Unlike `source_of`, an absence is always specific to one property —
        a `_default` absence would claim everything is missing."""
        assert pymat.lyso.absent("optical.scattering_length") is None

    def test_material_with_no_absences_returns_none(self):
        assert pymat.copper.absent("optical.reemit_qe") is None
        assert not pymat.copper.is_absent("optical.reemit_qe")


class TestLysoDeclaredAbsences:
    """The honest answers to the brief's P1 data asks (see
    docs/briefs/strata-optical-response.md)."""

    @pytest.mark.parametrize(
        "path,reason",
        [
            ("optical.emission_spectrum", "proprietary"),
            ("optical.refractive_index_dispersion", "proprietary"),
            ("optical.decay_components", "not-measured"),
            ("optical.absorption_length_matrix", "not-measured"),
            ("optical.reemit_qe", "not-measured"),
        ],
    )
    def test_lyso_declares_the_gap(self, path, reason):
        a = pymat.lyso.absent(path)
        assert a is not None, f"{path} should carry a declared absence"
        assert a.reason == reason
        assert a.note and len(a.note) > 80, "an absence without a searched-for note is a shrug"

    def test_self_absorption_split_is_half_measured_and_says_so(self):
        """ADR-0004 §5: populate both channels, or declare the missing one."""
        opt = pymat.lyso.properties.optical
        assert opt.absorption_length_reabs == 588.0  # measured, CC-BY
        assert opt.absorption_length_matrix is None  # not measured
        assert pymat.lyso.is_absent("optical.absorption_length_matrix")

    def test_measured_channel_is_cited(self):
        src = pymat.lyso.source_of("optical.absorption_length_reabs")
        assert src.citation == "bosca_lopez_2023"
        assert src.license == "CC-BY-4.0"

    def test_lumped_absorption_length_is_flagged_as_a_convention(self):
        """The 200 mm literal has a provenance chain, but it is a Monte-Carlo
        convention rather than a measurement, and the note must say so."""
        src = pymat.lyso.source_of("optical.absorption_length")
        assert "CONVENTION" in src.note

    def test_absorption_length_carries_its_sensitivity_warning(self):
        """A downstream 2D sweep showed this value is NOT second-order: it
        moves collection efficiency +17% at reflector R=0.97 but +53% at
        R=0.999, because the two parameters interact. The caveat is the kind of
        thing that gets tidied away, so it is pinned."""
        note = pymat.lyso.source_of("optical.absorption_length").note
        assert "SENSITIVITY" in note
        assert "interact" in note
        assert "Sweep this value" in note

    def test_bgo_dispersion_came_from_the_enricher(self):
        """ADR-0004 §10: bgo is in the refractiveindex.info enricher's scope,
        so its dispersion must arrive via the automated CC0 pull, never
        hand-authored. The citation is the check — a hand-written table would
        not carry this source row."""
        opt = pymat.bgo.properties.optical
        assert opt.refractive_index_dispersion is not None
        src = pymat.bgo.source_of("optical.refractive_index_dispersion")
        assert src.license == "CC0"
        assert "refractiveindex.info" in src.citation or "refractiveindex.info" in src.ref

    def test_bgo_scalar_understates_n_at_the_blue_end(self):
        """Why running the enricher mattered: the single scalar was fitted near
        the emission peak, so a monochromatic-at-peak simulation is roughly
        right, but anything sampling the blue edge of the band gets a critical
        angle built on an n that is ~2% low."""
        opt = pymat.bgo.properties.optical
        assert opt.refractive_index == 2.15
        assert opt.n_at(420) == pytest.approx(2.198, abs=0.005)
        assert opt.n_at(480) == pytest.approx(2.154, abs=0.005)
        assert opt.n_at(420) > opt.refractive_index


class TestStaleAliasFixed:
    """#157 moved radiation_length to NuclearProperties; the short alias kept
    pointing at `optical.` until #243 (ADR-0004 §8)."""

    def test_short_alias_resolves_to_nuclear(self):
        from pymat.sources import resolve_path

        assert resolve_path("radiation_length") == "nuclear.radiation_length"
        assert resolve_path("interaction_length") == "nuclear.interaction_length"


class TestSidecarMergeIsPartialNotWholesale:
    """A child declaring its OWN entry must keep the parent's other entries.

    Found by mutation audit: replacing `{**parent, **child}` with
    `dict(child)` in the loader left all 1217 tests green. The existing
    override test used the SAME key on parent and child, where a merge and a
    replacement are indistinguishable — the distinguishing case is DISJOINT
    keys, which nothing exercised.

    Failure mode if this regresses: a material that declares one absence
    silently loses every absence and citation it inherited. Nothing raises;
    provenance just quietly thins out down the tree.
    """

    def _load(self, tmp_path, body):
        p = tmp_path / "m.toml"
        p.write_text(dedent(body))
        return load_toml(p)

    def test_child_absences_merge_with_disjoint_parent_absences(self, tmp_path):
        mats = self._load(
            tmp_path,
            """
            [x]
            name = "X"
            [x._absent]
            "optical.reemit_qe" = { reason = "not-measured" }
            "optical.decay_components" = { reason = "not-measured" }
            [x.child]
            name = "Child"
            [x.child._absent]
            "optical.emission_spectrum" = { reason = "proprietary" }
            """,
        )
        child = mats["x"]._children["child"]
        assert sorted(child._absent) == [
            "optical.decay_components",
            "optical.emission_spectrum",
            "optical.reemit_qe",
        ]
        assert child.is_absent("optical.reemit_qe"), "inherited absence was dropped"
        assert child.is_absent("optical.emission_spectrum"), "own absence missing"

    def test_child_sources_merge_with_disjoint_parent_sources(self, tmp_path):
        """Same shape, same risk, for `_sources` — audited together because a
        gap in one implies a gap in the other."""
        mats = self._load(
            tmp_path,
            """
            [x]
            name = "X"
            [x._sources]
            "optical.light_yield" = { citation = "a", kind = "doi", ref = "10.1/a", license = "CC0"}
            [x.child]
            name = "Child"
            [x.child._sources]
            "optical.decay_time" = { citation = "b", kind = "doi", ref = "10.1/b", license = "CC0" }
            """,
        )
        child = mats["x"]._children["child"]
        assert child.source_of("optical.light_yield").citation == "a", "inherited source dropped"
        assert child.source_of("optical.decay_time").citation == "b"

    def test_the_real_corpus_exercises_the_merge(self):
        """`lyso.Ce` declares its own `_sources` rows while `lyso` declares
        others, so the shipped data depends on this merge rather than only the
        synthetic fixtures above."""
        own = pymat.lyso.Ce.source_of("optical.rise_time")
        inherited = pymat.lyso.Ce.source_of("optical.absorption_length_reabs")
        assert own is not None and own.citation == "seifert_2012"
        assert inherited is not None and inherited.citation == "bosca_lopez_2023"
        assert pymat.lyso.Ce.is_absent("optical.emission_spectrum")


class TestIntrinsicResolutionProvenance:
    """`intrinsic_resolution` is a DERIVED quantity, and the schema has to make
    that visible or it will be compared across incompatible extractions.

    It is the residual after subtracting an assumed photostatistical term, so
    two labs can publish different values for the same crystal purely by using
    different photodetectors. A consumer comparing their own extracted value
    against a literature one is comparing two numbers that were each produced
    under different assumptions — the same class of error as comparing two
    differently-normalised crosstalk figures.
    """

    def test_lso_value_carries_its_extraction_method(self):
        src = pymat.lso.Ce.source_of("optical.intrinsic_resolution_pct_at_662keV")
        assert src.ref == "10.1016/j.phpro.2011.11.035"
        # The method is the load-bearing part, not the number.
        for token in ("N_pe = 6610", "EXTRACTION METHOD", "transfer term assumed zero"):
            assert token in src.note, token

    def test_the_uncertainty_is_not_the_papers_error_bar(self):
        """The paper quotes ±0.3 on the TOTAL. The ±1.0 here is a deliberate
        widening for extraction-assumption and sample-to-sample spread, and the
        note must say so — otherwise it reads as a measurement precision it is
        not."""
        opt = pymat.lso.Ce.properties.optical
        assert opt.intrinsic_resolution_pct_at_662keV.nominal_value == pytest.approx(7.7)
        assert opt.intrinsic_resolution_pct_at_662keV.std_dev == pytest.approx(1.0)
        note = pymat.lso.Ce.source_of("optical.intrinsic_resolution_pct_at_662keV").note
        assert "NOT THE PAPER ERROR BAR" in note

    def test_511_kev_is_declared_absent_on_both_materials(self):
        for mat in (pymat.lso.Ce, pymat.lyso):
            a = mat.absent("optical.intrinsic_resolution_pct_at_511keV")
            assert a is not None and a.reason == "not-measured"

    def test_lyso_does_not_silently_inherit_the_lso_number(self):
        """LYSO is expected to be BETTER than LSO, so borrowing the LSO figure
        would bias high. The absence says so rather than leaving a consumer to
        assume they are interchangeable."""
        assert pymat.lyso.properties.optical.intrinsic_resolution_pct_at_662keV is None
        note = pymat.lyso.absent("optical.intrinsic_resolution_pct_at_662keV").note
        assert "BIASED HIGH" in note

    def test_non_proportionality_is_the_stated_cause(self):
        assert pymat.lso.Ce.properties.optical.non_proportionality == 43.0
        assert pymat.lso.Ce.source_of("optical.non_proportionality") is not None
