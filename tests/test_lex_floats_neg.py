"""Test lexer for floats and negative numbers."""

import pytest
from rpncalc.lexer import Lexer


def test_lex_float():
    """Tokenize a float number."""
    lexer = Lexer("3.14")
    tokens = lexer.tokenize()
    assert tokens == [("FLOAT", 3.14)]


def test_lex_negative_int():
    """Tokenize a negative integer."""
    lexer = Lexer("-5")
    tokens = lexer.tokenize()
    assert tokens == [("INT", -5)]


def test_lex_negative_float():
    """Tokenize a negative float."""
    lexer = Lexer("-2.0")
    tokens = lexer.tokenize()
    assert tokens == [("FLOAT", -2.0)]


def test_lex_mixed_numbers():
    """Tokenize mixed positive, negative, int, and float."""
    lexer = Lexer("1 3.14 -5 -2.0")
    tokens = lexer.tokenize()
    assert tokens == [("INT", 1), ("FLOAT", 3.14), ("INT", -5), ("FLOAT", -2.0)]


def test_lex_negative_with_spaces():
    """Tokenize negative numbers with surrounding whitespace."""
    lexer = Lexer("  -10  ")
    tokens = lexer.tokenize()
    assert tokens == [("INT", -10)]
