"""Test lexer for positive integers."""

import pytest
from rpncalc.lexer import Lexer


def test_lex_single_int():
    """Tokenize a single positive integer."""
    lexer = Lexer("42")
    tokens = lexer.tokenize()
    assert tokens == [("INT", 42)]


def test_lex_multiple_ints():
    """Tokenize multiple positive integers separated by whitespace."""
    lexer = Lexer("1 2 3")
    tokens = lexer.tokenize()
    assert tokens == [("INT", 1), ("INT", 2), ("INT", 3)]


def test_lex_ints_with_spaces():
    """Tokenize integers with various whitespace."""
    lexer = Lexer("10  20   30")
    tokens = lexer.tokenize()
    assert tokens == [("INT", 10), ("INT", 20), ("INT", 30)]


def test_lex_ints_with_newlines():
    """Tokenize integers separated by newlines."""
    lexer = Lexer("1\n2\n3")
    tokens = lexer.tokenize()
    assert tokens == [("INT", 1), ("INT", 2), ("INT", 3)]
