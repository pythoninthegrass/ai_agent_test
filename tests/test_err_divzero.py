"""Test division by zero error."""

import pytest
from rpncalc.lexer import Lexer
from rpncalc.eval import Eval, RpnError


def test_div_zero_int():
    """5 0 / raises RpnError."""
    lexer = Lexer("5 0 /")
    tokens = lexer.tokenize()
    evaluator = Eval(tokens)
    with pytest.raises(RpnError) as exc_info:
        evaluator.eval()
    assert "division by zero" in str(exc_info.value).lower() or "zero" in str(exc_info.value).lower()


def test_div_zero_float():
    """3.14 0.0 / raises RpnError."""
    lexer = Lexer("3.14 0.0 /")
    tokens = lexer.tokenize()
    evaluator = Eval(tokens)
    with pytest.raises(RpnError) as exc_info:
        evaluator.eval()
    assert "division by zero" in str(exc_info.value).lower() or "zero" in str(exc_info.value).lower()


def test_div_zero_in_expression():
    """10 2 0 / + raises RpnError."""
    lexer = Lexer("10 2 0 /")
    tokens = lexer.tokenize()
    evaluator = Eval(tokens)
    with pytest.raises(RpnError) as exc_info:
        evaluator.eval()
