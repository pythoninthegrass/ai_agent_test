"""Test extended operators: % ** // (modulo, power, floor-div)."""

import pytest
from rpncalc.lexer import Lexer
from rpncalc.eval import Eval, RpnError


def test_modulo_operator():
    """% operator computes modulo."""
    lexer = Lexer("7 3 %")
    tokens = lexer.tokenize()
    evaluator = Eval(tokens)
    result = evaluator.eval()
    assert result == 1


def test_modulo_negative():
    """% operator works with negative numbers (Python semantics: -7 % 3 = 2)."""
    lexer = Lexer("-7 3 %")
    tokens = lexer.tokenize()
    evaluator = Eval(tokens)
    result = evaluator.eval()
    # Python's modulo returns a result with the same sign as the divisor
    assert result == 2


def test_power_operator():
    """** operator computes power."""
    lexer = Lexer("2 3 **")
    tokens = lexer.tokenize()
    evaluator = Eval(tokens)
    result = evaluator.eval()
    assert result == 8


def test_power_float():
    """** operator works with floats."""
    lexer = Lexer("4 0.5 **")
    tokens = lexer.tokenize()
    evaluator = Eval(tokens)
    result = evaluator.eval()
    assert result == 2.0


def test_floor_div_operator():
    """// operator computes floor division."""
    lexer = Lexer("7 2 //")
    tokens = lexer.tokenize()
    evaluator = Eval(tokens)
    result = evaluator.eval()
    assert result == 3


def test_floor_div_negative():
    """// operator works with negative numbers."""
    lexer = Lexer("-7 2 //")
    tokens = lexer.tokenize()
    evaluator = Eval(tokens)
    result = evaluator.eval()
    assert result == -4


def test_extended_ops_with_floats():
    """Extended operators work with floats."""
    lexer = Lexer("10.5 3.5 %")
    tokens = lexer.tokenize()
    evaluator = Eval(tokens)
    result = evaluator.eval()
    assert result == 0.0


def test_extended_ops_mixed():
    """Mix of extended and basic operators."""
    lexer = Lexer("10 3 % 2 **")
    tokens = lexer.tokenize()
    evaluator = Eval(tokens)
    result = evaluator.eval()
    # (10 % 3) ** 2 = 1 ** 2 = 1
    assert result == 1


def test_all_operators_together():
    """Test all operators work together."""
    lexer = Lexer("2 3 + 4 5 * -")
    tokens = lexer.tokenize()
    evaluator = Eval(tokens)
    result = evaluator.eval()
    # (2 + 3) - (4 * 5) = 5 - 20 = -15
    assert result == -15


def test_extended_ops_stack_underflow():
    """Extended operators raise RpnError on underflow."""
    lexer = Lexer("5 %")
    tokens = lexer.tokenize()
    evaluator = Eval(tokens)
    with pytest.raises(RpnError) as exc_info:
        evaluator.eval()
    assert "stack underflow" in str(exc_info.value).lower()


def test_extended_ops_empty_stack():
    """Extended operators raise RpnError on empty stack."""
    lexer = Lexer("%")
    tokens = lexer.tokenize()
    evaluator = Eval(tokens)
    with pytest.raises(RpnError) as exc_info:
        evaluator.eval()
    assert "stack underflow" in str(exc_info.value).lower()
