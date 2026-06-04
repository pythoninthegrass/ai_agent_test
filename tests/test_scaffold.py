"""Test that the rpncalc package can be imported."""


def test_import_package():
    """A trivial test that imports the package."""
    import rpncalc
    from rpncalc import Lexer, Eval
    assert rpncalc is not None
    assert Lexer is not None
    assert Eval is not None
