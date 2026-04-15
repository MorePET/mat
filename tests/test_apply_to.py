"""
Test suite for Material.apply_to() error handling.

Tests that apply_to() works with:
- build123d Shapes (full features)
- Custom objects (material attribute only)
- Error cases (immutable objects)
"""

import pytest

from pymat import Material


class TestApplyToErrorHandling:
    """Test apply_to() with various object types."""

    def test_apply_to_build123d_shape(self):
        """Test applying material to build123d Shape."""
        pytest.importorskip("build123d")

        from build123d import Box

        from pymat import stainless

        shape = Box(10, 10, 10)
        result = stainless.apply_to(shape)

        # Should set all attributes
        assert result is shape
        assert shape.material == stainless
        assert shape.color is not None
        assert shape.mass > 0

    def test_apply_to_custom_object(self):
        """Test applying material to custom object."""
        mat = Material(name="Test")
        mat.density = 2.5

        class CustomPart:
            def __init__(self):
                self.name = "test"

        obj = CustomPart()
        result = mat.apply_to(obj)

        # Should only set material attribute
        assert result is obj
        assert obj.material == mat
        assert not hasattr(obj, "color")  # No color set
        assert not hasattr(obj, "mass")  # No mass set

    def test_apply_to_dict_like_object(self):
        """Test applying material to object with __setattr__."""
        mat = Material(name="Test")
        mat.density = 2.5

        class DictLikeObject:
            def __init__(self):
                self._attrs = {}

            def __setattr__(self, key, value):
                if key.startswith("_"):
                    object.__setattr__(self, key, value)
                else:
                    self._attrs[key] = value

            def __getattr__(self, key):
                return self._attrs.get(key)

        obj = DictLikeObject()
        result = mat.apply_to(obj)

        assert result is obj
        assert obj.material == mat

    def test_apply_to_object_with_volume_but_no_color(self):
        """Test object that has volume but not color (partial build123d-like)."""
        mat = Material(name="Test")
        mat.density = 2.5

        class PartialShape:
            def __init__(self):
                self.volume = 1000  # mm³

        obj = PartialShape()
        result = mat.apply_to(obj)

        # Should set material, skip color/mass gracefully
        assert result is obj
        assert obj.material == mat
        assert not hasattr(obj, "color")

    def test_apply_to_object_with_color_but_no_volume(self):
        """Test object that has color but not volume."""
        mat = Material(name="Test")
        mat.density = 2.5

        class ColoredObject:
            def __init__(self):
                self.color = (1, 0, 0)

        obj = ColoredObject()
        result = mat.apply_to(obj)

        # Should set material, skip volume-dependent features
        assert result is obj
        assert obj.material == mat
        # Color might be updated since it exists

    def test_apply_to_immutable_object_fails(self):
        """Test that applying to immutable object raises TypeError."""
        mat = Material(name="Test")
        mat.density = 2.5

        # Integers are immutable
        with pytest.raises(TypeError, match="doesn't support attribute assignment"):
            mat.apply_to(42)

        # Strings are immutable
        with pytest.raises(TypeError, match="doesn't support attribute assignment"):
            mat.apply_to("test")

        # Tuples are immutable
        with pytest.raises(TypeError, match="doesn't support attribute assignment"):
            mat.apply_to((1, 2, 3))

    def test_apply_to_none_fails(self):
        """Test that applying to None raises TypeError."""
        mat = Material(name="Test")
        mat.density = 2.5

        with pytest.raises(TypeError, match="doesn't support attribute assignment"):
            mat.apply_to(None)

    def test_apply_to_with_readonly_attribute(self):
        """Test object with read-only material attribute."""
        mat = Material(name="Test")
        mat.density = 2.5

        class ReadOnlyObject:
            @property
            def material(self):
                return "readonly"

        obj = ReadOnlyObject()

        # Should fail because material is read-only
        with pytest.raises(TypeError):
            mat.apply_to(obj)

    def test_apply_to_chained_materials(self):
        """Test applying chained material to build123d shape."""
        pytest.importorskip("build123d")

        from build123d import Box

        from pymat import stainless

        shape = Box(10, 10, 10)
        stainless.s316L.electropolished.apply_to(shape)

        # Should preserve full hierarchy
        assert shape.material.name == "Stainless Steel 316L - Electropolished"
        assert (
            shape.material.path == "stainless.s316L.electropolished"
        )  # Preserves case from TOML key
        assert shape.mass > 0

    def test_apply_to_without_density(self):
        """Test applying material without density (no mass calculation)."""
        pytest.importorskip("build123d")

        from build123d import Box

        mat = Material(name="Unknown Material")  # No density
        shape = Box(10, 10, 10)

        mat.apply_to(shape)

        # Material should be set, but mass should be 0 or unset
        assert shape.material == mat
        assert shape.color is not None
        # Mass might be 0 or previous value, just shouldn't crash


class TestApplyToTransparency:
    """Test that apply_to() correctly sets alpha from transmission."""

    def test_apply_to_sets_alpha_from_transmission(self):
        """Test that transmission=0.9 results in alpha=0.1."""
        pytest.importorskip("build123d")

        from build123d import Box

        # Create a transparent material (90% transmission = 10% alpha)
        glass = Material(
            name="Glass", pbr={"base_color": (0.9, 0.95, 1.0, 1.0), "transmission": 0.9}
        )

        shape = Box(10, 10, 10)
        glass.apply_to(shape)

        # Alpha should be 1 - transmission = 1 - 0.9 = 0.1
        assert shape.color is not None
        r, g, b, alpha = shape.color
        assert r == pytest.approx(0.9, rel=0.01)
        assert g == pytest.approx(0.95, rel=0.01)
        assert b == pytest.approx(1.0, rel=0.01)
        assert alpha == pytest.approx(0.1, rel=0.01), f"Expected alpha=0.1, got {alpha}"

    def test_apply_to_opaque_material_has_alpha_one(self):
        """Test that transmission=0 (opaque) results in alpha=1."""
        pytest.importorskip("build123d")

        from build123d import Box

        # Create an opaque material (transmission=0)
        steel = Material(
            name="Steel", pbr={"base_color": (0.5, 0.5, 0.5, 1.0), "transmission": 0.0}
        )

        shape = Box(10, 10, 10)
        steel.apply_to(shape)

        # Alpha should be 1 - transmission = 1 - 0 = 1.0
        assert shape.color is not None
        r, g, b, alpha = shape.color
        assert alpha == pytest.approx(1.0, rel=0.01), f"Expected alpha=1.0, got {alpha}"

    def test_apply_to_half_transparent(self):
        """Test that transmission=0.5 results in alpha=0.5."""
        pytest.importorskip("build123d")

        from build123d import Box

        # Create a half-transparent material
        frosted = Material(
            name="Frosted Glass", pbr={"base_color": (0.8, 0.8, 0.8, 1.0), "transmission": 0.5}
        )

        shape = Box(10, 10, 10)
        frosted.apply_to(shape)

        # Alpha should be 1 - transmission = 1 - 0.5 = 0.5
        assert shape.color is not None
        r, g, b, alpha = shape.color
        assert alpha == pytest.approx(0.5, rel=0.01), f"Expected alpha=0.5, got {alpha}"


class TestApplyToReturnValue:
    """Test that apply_to() returns the object for chaining."""

    def test_return_value_allows_chaining(self):
        """Test that apply_to() returns object for method chaining."""
        pytest.importorskip("build123d")

        from build123d import Box

        from pymat import aluminum

        # Should allow chaining
        shape = aluminum.apply_to(Box(10, 10, 10))

        assert shape.material == aluminum
        assert isinstance(shape.volume, (int, float))

    def test_return_value_custom_object(self):
        """Test return value for custom objects."""
        mat = Material(name="Test")

        class Part:
            pass

        obj = Part()
        result = mat.apply_to(obj)

        assert result is obj
        assert result.material == mat
