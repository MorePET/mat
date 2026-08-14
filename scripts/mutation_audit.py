"""Mutation audit — break the thing a gate guards, run the suite, see if it notices.

A test the wrong model passes is not a weak test, it is a NON-TEST. Reading a
test cannot tell you which you have; only running it against the failure it
claims to catch can. This script does that mechanically.

    python scripts/mutation_audit.py

Each entry patches one line of source, runs the full suite, restores the file,
and reports whether anything failed. `** NON-TEST **` means the suite is blind
to that defect.

Found on first use (#243): `_absent` sidecar inheritance. A child declaring its
own absence could silently drop every absence it inherited, and all 1217 tests
stayed green — the existing override test used the SAME key on parent and
child, where a merge and a replacement are indistinguishable. The cross-language
parity gate missed it too, because no shipped material exercises that branch.

Add an entry whenever you add a gate you are relying on. The anchors are exact
source lines and will need updating as the code moves; a SKIP means the anchor
drifted, not that the gate is fine.
"""

import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
PY = ROOT / ".venv/bin/python"

MUTATIONS = [
    # (label, file, old, new)
    (
        "obliquity 1/cos -> cos",
        "src/pymat/properties.py",
        "        return min(40.0, 1.0 / math.cos(theta))",
        "        return min(40.0, math.cos(theta))",
    ),
    (
        "R_inf sign flip",
        "src/pymat/properties.py",
        "        return 100.0 * (1.0 + x - math.sqrt(x * x + 2.0 * x))",
        "        return 100.0 * (1.0 + x + math.sqrt(x * x + 2.0 * x))",
    ),
    (
        "thick branch 1/(a+b) -> 1/(a-b)",
        "src/pymat/properties.py",
        "            r = 1.0 / (a + b)",
        "            r = 1.0 / (a - b) if a != b else 1.0",
    ),
    (
        "K-M drops absorption (k:=0)",
        "src/pymat/properties.py",
        '        curve = _as_wl_curve(self.kubelka_munk, "k")\n        return None if curve is None else curve.interpolate(_to_nm(wavelength))',  # noqa: E501 - anchor must match source verbatim
        '        curve = _as_wl_curve(self.kubelka_munk, "k")\n        return None if curve is None else 0.0',  # noqa: E501 - anchor must match source verbatim
    ),
    (
        "Fresnel R drops k term",
        "src/pymat/properties.py",
        "        r = ((n - 1.0) ** 2 + k**2) / ((n + 1.0) ** 2 + k**2)",
        "        r = ((n - 1.0) ** 2) / ((n + 1.0) ** 2)",
    ),
    (
        "WavelengthCurve extrapolates instead of clamping",
        "src/pymat/curves.py",
        "    if x <= xs[0]:\n        if x < xs[0]:",
        "    if False:\n        if x < xs[0]:",
    ),
    (
        "curve sort validation removed",
        "src/pymat/curves.py",
        "    for a, b in zip(xs, xs[1:]):\n        if not a < b:",
        "    for a, b in zip(xs, xs[1:]):\n        if False:",
    ),
    (
        "wavelength Quantity magnitude taken raw",
        "src/pymat/properties.py",
        "            return float(wavelength.to(ureg.nanometer).magnitude)",
        "            return float(wavelength.magnitude)",
    ),
    (
        "_absent stops inheriting",
        "src/pymat/loader.py",
        "        absent = {**parent_absent, **parse_absent_table(raw_absent)}",
        "        absent = dict(parse_absent_table(raw_absent))",
    ),
    (
        "surface optical_contact index check removed",
        "src/pymat/surfaces.py",
        '        if self.coupling == "optical_contact" and self.coupling_index is None:',
        "        if False:",
    ),
]

results = []
for label, relpath, old, new in MUTATIONS:
    f = ROOT / relpath
    original = f.read_text()
    if old not in original:
        results.append((label, "SKIP - anchor not found"))
        continue
    f.write_text(original.replace(old, new, 1))
    try:
        proc = subprocess.run(
            [str(PY), "-m", "pytest", "tests/", "-x", "-q", "--no-header", "-p", "no:randomly"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=900,
        )
        detected = proc.returncode != 0
        tail = [line for line in proc.stdout.splitlines() if "passed" in line or "failed" in line]
        results.append(
            (
                label,
                ("PASS (detected)" if detected else "** NON-TEST **")
                + ("  " + tail[-1].strip() if tail else ""),
            )
        )
    finally:
        f.write_text(original)

print(f"\n{'MUTATION':<46} RESULT")
print("-" * 100)
for label, r in results:
    print(f"{label:<46} {r}")
