"""Tests for the catalog generator script."""

from __future__ import annotations

from pathlib import Path

import pytest


class TestCatalogGenerator:
    def test_generates_root_index(self, tmp_path):
        from scripts.generate_catalog import generate

        generate(tmp_path, skip_thumbnails=True)
        readme = tmp_path / "README.md"
        assert readme.exists()
        content = readme.read_text()
        assert "Material Catalog" in content
        assert "Metals" in content

    def test_generates_category_dirs(self, tmp_path):
        from scripts.generate_catalog import generate

        generate(tmp_path, skip_thumbnails=True)
        assert (tmp_path / "metals" / "README.md").exists()
        assert (tmp_path / "plastics" / "README.md").exists()
        assert (tmp_path / "scintillators" / "README.md").exists()

    def test_generates_material_pages(self, tmp_path):
        from scripts.generate_catalog import generate

        generate(tmp_path, skip_thumbnails=True)
        # stainless should have a page
        assert (tmp_path / "metals" / "stainless.md").exists()
        content = (tmp_path / "metals" / "stainless.md").read_text()
        assert "Stainless Steel" in content
        assert "Density" in content or "Roughness" in content

    def test_material_page_has_vis_section(self, tmp_path):
        from scripts.generate_catalog import generate

        generate(tmp_path, skip_thumbnails=True)
        content = (tmp_path / "metals" / "stainless.md").read_text()
        # stainless has [vis] with source_id
        assert "mat-vis" in content or "ambientcg" in content

    def test_material_page_has_composition(self, tmp_path):
        from scripts.generate_catalog import generate

        generate(tmp_path, skip_thumbnails=True)
        content = (tmp_path / "metals" / "stainless.md").read_text()
        assert "Composition" in content
        assert "Fe" in content
        assert "Cr" in content

    def test_uncertainty_composition_renders(self, tmp_path):
        """Al 6063 has ufloat composition — should render without crash."""
        from scripts.generate_catalog import generate

        generate(tmp_path, skip_thumbnails=True)
        page = tmp_path / "metals" / "aluminum-a6063.md"
        assert page.exists()
        content = page.read_text()
        assert "Si" in content
        # Should show uncertainty notation
        assert "±" in content

    def test_category_index_has_table(self, tmp_path):
        from scripts.generate_catalog import generate

        generate(tmp_path, skip_thumbnails=True)
        content = (tmp_path / "metals" / "README.md").read_text()
        assert "| Material |" in content
        assert "Stainless Steel" in content

    def test_total_material_count(self, tmp_path):
        from scripts.generate_catalog import generate

        generate(tmp_path, skip_thumbnails=True)
        md_files = list(tmp_path.rglob("*.md"))
        # Should have at least 90+ pages (96 materials + 7 category indexes + 1 root)
        assert len(md_files) > 90
