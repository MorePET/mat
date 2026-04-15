"""
Global material registry for direct access.

Allows materials to be accessed directly by key:
    from pymat import s304, s316L, lyso, fr4

All materials are stored in _REGISTRY when created (if no name collision).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from .core import Material


# Global registry: key -> Material instance
_REGISTRY: Dict[str, Material] = {}


def register(key: str, material: Material) -> None:
    """
    Register a material for direct access.

    Args:
        key: Access key (e.g., "s304", "lyso", "fr4")
        material: Material instance to register

    Note:
        Only registers if key doesn't already exist (prevents collisions).
    """
    if key and key not in _REGISTRY:
        _REGISTRY[key] = material


def get(key: str) -> Optional[Material]:
    """Get a registered material by key."""
    return _REGISTRY.get(key)


def list_all() -> Dict[str, Material]:
    """Get all registered materials."""
    return dict(_REGISTRY)


def clear() -> None:
    """Clear all registered materials (for testing)."""
    global _REGISTRY
    _REGISTRY.clear()
