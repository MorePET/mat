"""
Atomic weights for chemical elements.

Mirror of mat-rs/src/elements.rs to keep the Python and Rust APIs
symmetric — Monte Carlo consumers that use both (`rs-materials` for
transport, `pymat` for CAD) get the same numeric answers.

Values are in g/mol, rounded to IUPAC's standard atomic weight (2021
recommendations) at four significant figures. Exotic elements beyond
uranium are not listed — add as needed.
"""

from __future__ import annotations

import re

# Standard atomic weights in g/mol. Single source of truth for
# composition-derived molar mass calculations on `Material`.
ATOMIC_WEIGHT: dict[str, float] = {
    "H": 1.008,
    "He": 4.003,
    "Li": 6.941,
    "Be": 9.012,
    "B": 10.81,
    "C": 12.01,
    "N": 14.01,
    "O": 16.00,
    "F": 19.00,
    "Ne": 20.18,
    "Na": 22.99,
    "Mg": 24.31,
    "Al": 26.98,
    "Si": 28.09,
    "P": 30.97,
    "S": 32.07,
    "Cl": 35.45,
    "Ar": 39.95,
    "K": 39.10,
    "Ca": 40.08,
    "Sc": 44.96,
    "Ti": 47.87,
    "V": 50.94,
    "Cr": 52.00,
    "Mn": 54.94,
    "Fe": 55.85,
    "Co": 58.93,
    "Ni": 58.69,
    "Cu": 63.55,
    "Zn": 65.38,
    "Ga": 69.72,
    "Ge": 72.63,
    "As": 74.92,
    "Se": 78.97,
    "Br": 79.90,
    "Kr": 83.80,
    "Rb": 85.47,
    "Sr": 87.62,
    "Y": 88.91,
    "Zr": 91.22,
    "Nb": 92.91,
    "Mo": 95.95,
    "Tc": 98.0,
    "Ru": 101.1,
    "Rh": 102.9,
    "Pd": 106.4,
    "Ag": 107.9,
    "Cd": 112.4,
    "In": 114.8,
    "Sn": 118.7,
    "Sb": 121.8,
    "Te": 127.6,
    "I": 126.9,
    "Xe": 131.3,
    "Cs": 132.9,
    "Ba": 137.3,
    "La": 138.9,
    "Ce": 140.1,
    "Pr": 140.9,
    "Nd": 144.2,
    "Pm": 145.0,
    "Sm": 150.4,
    "Eu": 152.0,
    "Gd": 157.3,
    "Tb": 158.9,
    "Dy": 162.5,
    "Ho": 164.9,
    "Er": 167.3,
    "Tm": 168.9,
    "Yb": 173.0,
    "Lu": 175.0,
    "Hf": 178.5,
    "Ta": 180.9,
    "W": 183.8,
    "Re": 186.2,
    "Os": 190.2,
    "Ir": 192.2,
    "Pt": 195.1,
    "Au": 197.0,
    "Hg": 200.6,
    "Tl": 204.4,
    "Pb": 207.2,
    "Bi": 209.0,
    "Po": 209.0,
    "At": 210.0,
    "Rn": 222.0,
    "Fr": 223.0,
    "Ra": 226.0,
    "Ac": 227.0,
    "Th": 232.0,
    "Pa": 231.0,
    "U": 238.0,
}


_FORMULA_TOKEN = re.compile(r"([A-Z][a-z]?)(\d+\.?\d*)?")


def parse_formula(formula: str) -> dict[str, float]:
    """
    Parse a chemical formula into an element-count dict.

    Supports fractional stoichiometry (`Lu1.8Y0.2SiO5`) and strips
    dopant suffixes after `:` (`LYSO:Ce` → `LYSO`). Repeated elements
    are summed. Returns an empty dict if the formula contains no
    recognizable element tokens.

    Raises `ValueError` if the formula contains an element symbol
    that is not in `ATOMIC_WEIGHT`. This is strict on purpose:
    callers that want graceful degradation should catch it.
    """
    clean = formula.split(":", 1)[0]
    counts: dict[str, float] = {}
    for sym, count_str in _FORMULA_TOKEN.findall(clean):
        if not sym:
            continue
        if sym not in ATOMIC_WEIGHT:
            raise ValueError(f"Unknown element symbol {sym!r} in formula {formula!r}")
        count = float(count_str) if count_str else 1.0
        counts[sym] = counts.get(sym, 0.0) + count
    return counts


def compute_molar_mass(formula: str) -> float:
    """
    Compute molar mass (g/mol) of a chemical formula.

    For pure compounds with a well-defined formula unit. Not meaningful
    for alloys/mixtures whose TOML `composition` is stored as mass
    fractions — those have no single "molar mass". See ADR-0001.

    Raises `ValueError` for unknown element symbols or empty formulas.
    """
    counts = parse_formula(formula)
    if not counts:
        raise ValueError(f"No recognizable elements in formula {formula!r}")
    return sum(ATOMIC_WEIGHT[el] * count for el, count in counts.items())
