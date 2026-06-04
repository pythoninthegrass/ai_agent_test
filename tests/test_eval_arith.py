"""Test RPN evaluation for arithmetic operators."""

import pytest
from rpncalc.lexer import Lexer
from rpncalc.eval import Eval, RpnError


def test_eval_simple_add():
    """Evaluate 3 4 + -> 7."""
    lexer = Lexer("3 4 +")
    tokens = lexer.tokenize()
    evaluator = Eval(tokens)
    result = evaluator.eval()
    assert result == 7


def test_eval_simple_subtract():
    """Evaluate 10 3 - -> 7."""
    lexer = Lexer("10 3 -")
    tokens = lexer.tokenize()
    evaluator = Eval(tokens)
    result = evaluator.eval()
    assert result == 7


def test_eval_simple_multiply():
    """Evaluate 5 6 * -> 30."""
    lexer = Lexer("5 6 *")
    tokens = lexer.tokenize()
    evaluator = Eval(tokens)
    result = evaluator.eval()
    assert result == 30


def test_eval_simple_divide():
    """Evaluate 20 4 / -> 5."""
    lexer = Lexer("20 4 /")
    tokens = lexer.tokenize()
    evaluator = Eval(tokens)
    result = evaluator.eval()
    assert result == 5


def test_eval_complex_expression():
    """Evaluate 3 4 + 2 * -> 14."""
    lexer = Lexer("3 4 + 2 *")
    tokens = lexer.tokenize()
    evaluator = Eval(tokens)
    result = evaluator.eval()
    assert result == 14


def test_eval_multiple_operations():
    """Evaluate 1 2 + 3 + -> 6."""
    lexer = Lexer("1 2 + 3 +")
    tokens = lexer.tokenize()
    evaluator = Eval(tokens)
    result = evaluator.eval()
    assert result == 6
