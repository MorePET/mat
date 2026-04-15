"""
Material enrichment from external data sources.

Currently supports:
- periodictable: NIST element and compound data
- Future: Materials Project API, MatWeb scraping, etc.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .core import Material


def enrich_from_periodictable(material: Material) -> Material:
    """
    Fill in missing material properties from periodictable library.

    Uses chemical formula to look up elemental data and estimate:
    - density (from empirical formula-based estimation)
    - composition (atomic fractions)
    - molecular weight

    Args:
        material: Material instance to enrich

    Returns:
        The enriched material (modified in-place)

    Example:
        lyso = Material("LYSO", formula="Lu1.8Y0.2SiO5")
        enrich_from_periodictable(lyso)
        print(lyso.properties.mechanical.density)  # should be ~7.1
    """
    if not material.formula:
        return material

    try:
        import periodictable as pt
    except ImportError:
        raise ImportError("periodictable not installed. Install with: pip install periodictable")

    try:
        formula = pt.formula(material.formula)
    except Exception as e:
        print(f"Warning: Could not parse formula '{material.formula}': {e}")
        return material

    # Set density if not already set and available
    if not material.properties.mechanical.density and formula.density:
        material.properties.mechanical.density = formula.density

    # Set composition if not already set
    if not material.composition and formula.atoms:
        material.composition = {str(el): count for el, count in formula.atoms.items()}

    return material


def enrich_from_matproj(
    material: Material,
    api_key: str,
    properties: list[str] | None = None,
) -> Material:
    """
    Fetch properties from Materials Project API.

    Requires a free API key from https://materialsproject.org/

    Args:
        material: Material instance to enrich
        api_key: Materials Project API key
        properties: List of properties to fetch (default: common ones)

    Returns:
        The enriched material (modified in-place)

    Example:
        al2o3 = Material("Alumina", formula="Al2O3")
        enrich_from_matproj(al2o3, api_key="YOUR_KEY")
        print(al2o3.properties.mechanical.density)
    """
    if not material.formula:
        return material

    try:
        from pymatgen.ext.matproj import MPRester
    except ImportError as e:
        raise ImportError("pymatgen not installed. Install with: pip install pymatgen") from e

    if properties is None:
        properties = [
            "density",
            "band_gap",
            "formation_energy",
            "material_id",
        ]

    try:
        with MPRester(api_key) as mpr:
            results = mpr.summary.search(
                formula=material.formula,
                fields=properties,
            )

            if results:
                result = results[0]  # Take most stable phase

                if "density" in result:
                    material.properties.mechanical.density = result["density"]

                # Store other properties in custom dict
                for key, value in result.items():
                    if key not in ("density",):
                        material.properties.custom[key] = value

    except Exception as e:
        print(f"Warning: Materials Project query failed: {e}")

    return material


def enrich_all(
    material: Material,
    use_periodictable: bool = True,
    matproj_api_key: Optional[str] = None,
) -> Material:
    """
    Enrich material from all available sources.

    Args:
        material: Material to enrich
        use_periodictable: Whether to query periodictable (default: True)
        matproj_api_key: Materials Project API key (optional)

    Returns:
        The enriched material
    """
    if use_periodictable:
        enrich_from_periodictable(material)

    if matproj_api_key:
        enrich_from_matproj(material, matproj_api_key)

    return material
