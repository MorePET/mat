"""Unit tests for tests/_visual_compare.py — the pixel-diff helper.

These run without Playwright / rendering; they exercise the comparator
logic against synthetic PIL images. The full render→compare pipeline is
pinned by tests/test_visual_regression.py (Playwright-gated).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from tests._visual_compare import (
    DEFAULT_RMS_TOLERANCE,
    _rms,
    assert_matches_baseline,
)


def _write_png(path: Path, color: tuple[int, int, int], size=(64, 64)) -> Path:
    img = Image.new("RGB", size, color)
    img.save(path, "PNG")
    return path


class TestRMS:
    def test_identical(self):
        assert _rms([128] * 10, [128] * 10) == 0.0

    def test_single_channel_off_by_one(self):
        # 10 pixels, each with Δ=1 → RMS = sqrt(10/10) = 1.0
        assert _rms([128] * 10, [129] * 10) == pytest.approx(1.0)

    def test_single_channel_off_by_ten(self):
        assert _rms([128] * 10, [138] * 10) == pytest.approx(10.0)

    def test_empty(self):
        """Zero-length inputs return 0.0 (not a division error)."""
        assert _rms([], []) == 0.0


class TestAssertMatchesBaseline:
    def test_identical_images_pass(self, tmp_path, monkeypatch):
        # Point the baseline dir at tmp
        monkeypatch.setattr("tests._visual_compare.BASELINE_DIR", tmp_path / "baselines")
        # Pre-create a baseline
        baseline_dir = tmp_path / "baselines"
        baseline_dir.mkdir()
        _write_png(baseline_dir / "sample.png", (100, 150, 200))

        actual = _write_png(tmp_path / "actual.png", (100, 150, 200))
        # Identical → RMS=0 → passes
        assert_matches_baseline(actual, "sample")

    def test_within_tolerance_passes(self, tmp_path, monkeypatch):
        monkeypatch.setattr("tests._visual_compare.BASELINE_DIR", tmp_path / "baselines")
        baseline_dir = tmp_path / "baselines"
        baseline_dir.mkdir()
        _write_png(baseline_dir / "sample.png", (128, 128, 128))

        # Slightly different: Δ=5 per channel → RMS=5, default tolerance is 8
        actual = _write_png(tmp_path / "actual.png", (133, 128, 128))
        assert_matches_baseline(actual, "sample")  # should pass

    def test_beyond_tolerance_fails(self, tmp_path, monkeypatch):
        monkeypatch.setattr("tests._visual_compare.BASELINE_DIR", tmp_path / "baselines")
        baseline_dir = tmp_path / "baselines"
        baseline_dir.mkdir()
        _write_png(baseline_dir / "sample.png", (128, 128, 128))

        # Δ=50 per channel → RMS ≈ 50 → well beyond default tolerance of 8
        actual = _write_png(tmp_path / "actual.png", (178, 178, 178))
        with pytest.raises(AssertionError, match="pixel RMS"):
            assert_matches_baseline(actual, "sample")

    def test_size_mismatch_fails(self, tmp_path, monkeypatch):
        monkeypatch.setattr("tests._visual_compare.BASELINE_DIR", tmp_path / "baselines")
        baseline_dir = tmp_path / "baselines"
        baseline_dir.mkdir()
        _write_png(baseline_dir / "sample.png", (0, 0, 0), size=(32, 32))

        actual = _write_png(tmp_path / "actual.png", (0, 0, 0), size=(64, 64))
        with pytest.raises(AssertionError, match="render size"):
            assert_matches_baseline(actual, "sample")

    def test_missing_baseline_skips(self, tmp_path, monkeypatch):
        """If no baseline is committed, skip with a helpful message
        pointing at MAT_VIS_UPDATE_BASELINES=1 — don't fail the suite
        on a missing baseline."""
        monkeypatch.setattr("tests._visual_compare.BASELINE_DIR", tmp_path / "baselines")
        actual = _write_png(tmp_path / "actual.png", (0, 0, 0))
        with pytest.raises(pytest.skip.Exception, match="No committed baseline"):
            assert_matches_baseline(actual, "never_generated")

    def test_update_mode_writes_baseline(self, tmp_path, monkeypatch):
        """MAT_VIS_UPDATE_BASELINES=1 copies the actual PNG to the
        baseline dir instead of comparing."""
        monkeypatch.setattr("tests._visual_compare.BASELINE_DIR", tmp_path / "baselines")
        monkeypatch.setenv("MAT_VIS_UPDATE_BASELINES", "1")
        actual = _write_png(tmp_path / "actual.png", (11, 22, 33))

        assert_matches_baseline(actual, "newly_generated")

        baseline = tmp_path / "baselines" / "newly_generated.png"
        assert baseline.exists()
        # Same content
        assert baseline.read_bytes() == actual.read_bytes()

    def test_tolerance_override(self, tmp_path, monkeypatch):
        """Caller can pass a lower tolerance to catch smaller drift."""
        monkeypatch.setattr("tests._visual_compare.BASELINE_DIR", tmp_path / "baselines")
        baseline_dir = tmp_path / "baselines"
        baseline_dir.mkdir()
        _write_png(baseline_dir / "sample.png", (128, 128, 128))

        # Δ=5 → RMS=5. Default tolerance 8 → pass. Pass tolerance=2 → fail.
        actual = _write_png(tmp_path / "actual.png", (133, 128, 128))
        assert_matches_baseline(actual, "sample")  # default passes
        with pytest.raises(AssertionError, match="exceeds tolerance"):
            assert_matches_baseline(actual, "sample", rms_tolerance=2.0)


def test_default_tolerance_is_sane():
    """Document the chosen tolerance so a refactor can't drop it
    silently. 8.0 per channel on 0..255 is ~3% — wide enough to
    absorb Chromium minor-version AA drift, narrow enough to catch
    a material rendering as grey (Δ ≈ 50+)."""
    assert 4.0 <= DEFAULT_RMS_TOLERANCE <= 15.0
