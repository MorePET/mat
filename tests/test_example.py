"""Example tests for py_mat."""


def test_example():
    """Example test that always passes."""
    assert True


def test_import():
    """Test that the package can be imported."""
    import py_mat  # noqa: F401 - renamed to project name by init-workspace.sh

    assert py_mat.__version__ == "0.1.0"
