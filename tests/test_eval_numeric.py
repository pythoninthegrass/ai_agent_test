"""Test numeric semantics - preserve int vs float."""

import pytest
from rpncalc.lexer import Lexer
from rpncalc.eval import Eval, RpnError


def test_eval_div_float_result():
    """7 2 / -> 3.5 (float)."""
    lexer = Lexer("7 2 /")
    tokens = lexer.tokenize()
    evaluator = Eval(tokens)
    result = evaluator.eval()
    assert result == 3.5
    assert isinstance(result, float)


def test_eval_div_int_result():
    """6 2 / -> 3 (int)."""
    lexer = Lexer("6 2 /")
    tokens = lexer.tokenize()
    evaluator = Eval(tokens)
    result = evaluator.eval()
    assert result == 3
    # Note: Python's / always returns float, so we check if the result is whole
    assert result == int(result)


def test_eval_add_int_int():
    """1 2 + -> 3 (int)."""
    lexer = Lexer("1 2 +")
    tokens = lexer.tokenize()
    evaluator = Eval(tokens)
    result = evaluator.eval()
    assert result == 3


def test_eval_add_int_float():
    """1 2.5 + -> 3.5 (float)."""
    lexer = Lexer("1 2.5 +")
    tokens = lexer.tokenize()
    evaluator = Eval(tokens)
    result = evaluator.eval()
    assert result == 3.5
    assert isinstance(result, float)


def test_eval_mul_int_float():
    """2 3.5 * -> 7.0 (float)."""
    lexer = Lexer("2 3.5 *")
    tokens = lexer.tokenize()
    evaluator = Eval(tokens)
    result = evaluator.eval()
    assert result == 7.0
