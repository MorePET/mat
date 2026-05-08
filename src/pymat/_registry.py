"""``pymat.materials`` — the canonical material registry surface.

A single object that's simultaneously:

- a ``Mapping[str, Material]`` — supports ``[name]``, ``in``, iteration,
  ``.keys()`` / ``.values()`` / ``.items()``, ``len(...)``;
- callable for lookup (``materials("name")``) and filter
  (``materials(category=..., grade=..., tags=[...], with_vis=...)``);
- type-checkable via ``Mapping`` protocol + overloaded ``__call__``
  signatures.

Mirrors ``pint.UnitRegistry``'s call/attr/subscript trifecta — same
shape downstream Python users have already encountered. Drops the
earlier ``pymat.lookup()`` proposal (it was redundant with the
callable form here).

Implementation note: this module is private (underscore prefix), but
the class's ``__module__`` is rewritten to ``pymat`` at the import
site so consumers see ``type(pymat.materials).__module__ == "pymat"``
and IDE auto-import / Sphinx land on the public path. Same convention
as :class:`pymat.vis.Vis` (closes #98 / mat-vis #282 inside py-mat's
own module surface).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import TYPE_CHECKING, overload

if TYPE_CHECKING:
    from pymat.core import Material


_CATEGORY_BASES_PROVIDER = None  # late-bound to avoid circular import


def _categories() -> dict[str, list[str]]:
    """Lazy access to ``pymat._CATEGORY_BASES`` so this module imports
    cleanly without forcing ``pymat`` to be fully initialised."""
    global _CATEGORY_BASES_PROVIDER
    if _CATEGORY_BASES_PROVIDER is None:
        import pymat

        _CATEGORY_BASES_PROVIDER = lambda: pymat._CATEGORY_BASES  # noqa: E731
    return _CATEGORY_BASES_PROVIDER()


class _Materials(Mapping[str, "Material"]):
    """The ``pymat.materials`` registry surface.

    See module docstring for the complete API contract.
    """

    # ── Mapping protocol ─────────────────────────────────────────

    def __getitem__(self, key: str) -> "Material":
        from pymat import _lookup

        return _lookup(key)

    def __iter__(self) -> Iterator[str]:
        from pymat import registry

        return iter(registry.list_all())

    def __len__(self) -> int:
        from pymat import registry

        return len(registry.list_all())

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        from pymat import _lookup

        try:
            _lookup(key)
            return True
        except KeyError:
            return False

    # ── Callable: lookup OR filter ───────────────────────────────

    @overload
    def __call__(self, name: str, /) -> "Material": ...

    @overload
    def __call__(
        self,
        *,
        category: str | None = None,
        grade: str | None = None,
        tags: list[str] | None = None,
        with_vis: bool | None = None,
    ) -> list["Material"]: ...

    def __call__(
        self,
        name: str | None = None,
        /,
        *,
        category: str | None = None,
        grade: str | None = None,
        tags: list[str] | None = None,
        with_vis: bool | None = None,
    ) -> "Material | list[Material]":
        """Lookup a single Material by name OR filter the registry.

        - ``materials("X")`` → exact-match lookup, returns one Material,
          raises ``KeyError`` (with fuzzy suggestions) on miss.
        - ``materials()`` → all materials, returns ``list[Material]``.
        - ``materials(category=..., grade=..., tags=[...], with_vis=...)``
          → AND-filtered list, possibly empty.

        Mixing positional ``name`` with filter kwargs raises ``TypeError`` —
        the intent is ambiguous (lookup-with-filter doesn't have a clear
        meaning), and the static overloads above also reject it.
        """
        from pymat import _lookup, registry

        if name is not None:
            # Reject mixed positional + filter — ambiguous semantics
            if any(v is not None for v in (category, grade, tags, with_vis)):
                raise TypeError(
                    "pymat.materials() cannot mix a positional name with filter "
                    "kwargs. Pass the name alone for lookup, or kwargs alone for "
                    "filtering — not both."
                )
            return _lookup(name)

        # Filter form — pull the full registry, apply AND across non-None
        # filters. Empty filters fall through and return everything.
        all_materials = registry.list_all()  # dict[str, Material]
        result = list(all_materials.values())

        if category is not None:
            cat_keys = set(_categories().get(category, []))
            result = [m for m in result if m._key in cat_keys or _key_in_category(m, cat_keys)]

        if grade is not None:
            result = [m for m in result if getattr(m, "grade", None) == grade]

        if tags is not None:
            required = set(tags)
            result = [m for m in result if required.issubset(set(getattr(m, "tags", []) or []))]

        if with_vis is not None:

            def _has_vis(m: "Material") -> bool:
                v = getattr(m, "vis", None)
                if v is None:
                    return False
                return bool(getattr(v, "has_mapping", False))

            result = [m for m in result if _has_vis(m) == with_vis]

        return result


def _key_in_category(material: "Material", cat_keys: set[str]) -> bool:
    """Walk parent chain — a child of a category-rooted material counts
    as in that category.

    The category mapping in ``pymat._CATEGORY_BASES`` lists root keys
    (``stainless``, ``aluminum``, ``lyso``, …); descendants
    (``s316L``, ``a6061.T6``) inherit category membership through
    their parent chain.
    """
    parent = getattr(material, "parent", None)
    while parent is not None:
        pkey = getattr(parent, "_key", None)
        if pkey in cat_keys:
            return True
        parent = getattr(parent, "parent", None)
    return False
