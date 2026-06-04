"""Test lexer for operators."""

import pytest
from rpncalc.lexer import Lexer


def test_lex_plus():
    """Tokenize the plus operator."""
    lexer = Lexer("+")
    tokens = lexer.tokenize()
    assert tokens == [("OP", "+")]


def test_lex_minus():
    """Tokenize the minus operator."""
    lexer = Lexer("-")
    tokens = lexer.tokenize()
    assert tokens == [("OP", "-")]


def test_lex_multiply():
    """Tokenize the multiply operator."""
    lexer = Lexer("*")
    tokens = lexer.tokenize()
    assert tokens == [("OP", "*")]


def test_lex_divide():
    """Tokenize the divide operator."""
    lexer = Lexer("/")
    tokens = lexer.tokenize()
    assert tokens == [("OP", "/")]


def test_lex_ops_with_numbers():
    """Tokenize operators mixed with numbers."""
    lexer = Lexer("3 4 +")
    tokens = lexer.tokenize()
    assert tokens == [("INT", 3), ("INT", 4), ("OP", "+")]


def test_lex_all_ops():
    """Tokenize all operators together."""
    lexer = Lexer("+ - * /")
    tokens = lexer.tokenize()
    assert tokens == [
        ("OP", "+"),
        ("OP", "-"),
        ("OP", "*"),
        ("OP", "/"),
    ]


def test_lex_ops_with_negative_numbers():
    """Tokenize operators with negative numbers."""
    lexer = Lexer("5 -3 +")
    tokens = lexer.tokenize()
    assert tokens == [("INT", 5), ("INT", -3), ("OP", "+")]


def test_lex_ops_with_floats():
    """Tokenize operators with floats."""
    lexer = Lexer("3.14 2.0 +")
    tokens = lexer.tokenize()
    assert tokens == [("FLOAT", 3.14), ("FLOAT", 2.0), ("OP", "+")]
