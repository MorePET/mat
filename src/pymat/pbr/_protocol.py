"""The `PbrSource` typing Protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class PbrSource(Protocol):
    """A renderable PBR material source.

    Any object implementing `to_dict()` is a valid `PbrSource`.
    The native `pymat.properties.PBRProperties` and the optional
    `threejs_materials.PbrProperties` both conform.

    Consumers (ocp_vscode, build123d viewers, custom renderers) should
    call `to_dict()` to get a Three.js `MeshPhysicalMaterial`-
    shaped dict, agnostic of which backend is providing the data. This
    keeps the rendering pipeline decoupled from how the material was
    sourced (TOML authored / runtime downloaded / MaterialX baked).

    See ADR-0002 for the design rationale.
    """

    def to_dict(self) -> dict:
        """Return a Three.js `MeshPhysicalMaterial` dict.

        Conforming implementations should use camelCase keys matching
        Three.js's expected parameter names (`color`, `metalness`,
        `roughness`, `transmission`, `opacity`, `transparent`, `emissive`,
        `ior`, `clearcoat`, `normalMap`, etc.) and omit fields whose
        value is the Three.js default.
        """
        ...
