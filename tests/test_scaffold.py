"""Test for milestone 1: scaffold."""

from rpncalc import __version__


def test_version() -> None:
    """Test that the package has a version."""
    assert isinstance(__version__, str)
    assert len(__version__) > 0
