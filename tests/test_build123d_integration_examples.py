"""Execute ``examples/build123d_integration.py`` top-to-bottom as a test.

The examples file is a cell-style script (``# %%`` markers) mirroring
how build123d's author writes his own examples. Running the full script
in pytest keeps it honest: if any API drifts, the example — which is
what consumers are copy-pasting — goes red before they do.

We shell out via ``runpy.run_path`` rather than splitting cells because
cell-order matters (later cells use objects defined earlier). The
network-touching cells catch their own exceptions so a flaky mat-vis
CDN doesn't redline the whole example suite.
"""

from __future__ import annotations

import runpy
from pathlib import Path

EXAMPLE_PATH = Path(__file__).parent.parent / "examples" / "build123d_integration.py"


def test_example_script_runs_end_to_end(capsys):
    """Every cell in ``examples/build123d_integration.py`` must execute
    without error. Assertions inside the cells are part of the contract
    — this test fails the moment any of them regress."""
    assert EXAMPLE_PATH.exists(), f"missing example: {EXAMPLE_PATH}"

    # Execute as a fresh script (mimics user running it top-to-bottom).
    # ``runpy.run_path`` gives us an isolated namespace and real exception
    # propagation — unlike ``exec`` which can hide import errors.
    result = runpy.run_path(str(EXAMPLE_PATH), run_name="__main__")

    # Smoke: the script should have defined the key bindings used in
    # cell 4 / 5 / 6. If a refactor silently drops one of these the
    # test fails with a clean "missing name" rather than a stack trace
    # buried inside runpy.
    for name in ("s304", "housing_mat", "stainless"):
        assert name in result, (
            f"example script didn't define {name!r} — cell order may have drifted"
        )

    # The completion line from the last cell should have reached stdout.
    out = capsys.readouterr().out
    assert "All cells completed." in out, (
        "example script did not reach its final cell — a middle cell likely errored"
    )


def test_example_is_up_to_date_with_api():
    """Guard that the example file references APIs that actually exist.
    Prevents stale copy-paste when module exports change."""
    import pymat
    from pymat import Material, search  # noqa: F401 — shape assertions

    # The cells touch these in order; if any is missing on the public
    # surface the script will fail at import time.
    assert hasattr(pymat, "search")
    assert callable(pymat.search)
    assert callable(getattr(pymat.__class__, "__getitem__", None))

    # Method-form adapters the example exercises.
    m = Material(name="probe")
    for method in ("to_threejs", "to_gltf", "export_mtlx"):
        assert callable(getattr(m.vis, method)), f"Vis.{method} missing — example will break"
