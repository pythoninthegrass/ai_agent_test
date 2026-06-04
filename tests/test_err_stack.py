"""Test stack error handling."""

import pytest
from rpncalc.lexer import Lexer
from rpncalc.eval import Eval, RpnError


def test_underflow_single_op():
    """+ with one operand raises RpnError."""
    lexer = Lexer("5 +")
    tokens = lexer.tokenize()
    evaluator = Eval(tokens)
    with pytest.raises(RpnError) as exc_info:
        evaluator.eval()
    assert "stack underflow" in str(exc_info.value).lower()


def test_underflow_two_ops():
    """+ with no operands raises RpnError."""
    lexer = Lexer("+")
    tokens = lexer.tokenize()
    evaluator = Eval(tokens)
    with pytest.raises(RpnError) as exc_info:
        evaluator.eval()
    assert "stack underflow" in str(exc_info.value).lower()


def test_leftover_operands():
    """Extra operands on stack raises RpnError."""
    lexer = Lexer("1 2 3 +")
    tokens = lexer.tokenize()
    evaluator = Eval(tokens)
    with pytest.raises(RpnError) as exc_info:
        evaluator.eval()
    assert "leftover" in str(exc_info.value).lower() or "stack" in str(exc_info.value).lower()


def test_underflow_minus():
    """- with one operand raises RpnError."""
    lexer = Lexer("5 -")
    tokens = lexer.tokenize()
    evaluator = Eval(tokens)
    with pytest.raises(RpnError) as exc_info:
        evaluator.eval()
    assert "stack underflow" in str(exc_info.value).lower()


def test_underflow_multiply():
    """* with one operand raises RpnError."""
    lexer = Lexer("5 *")
    tokens = lexer.tokenize()
    evaluator = Eval(tokens)
    with pytest.raises(RpnError) as exc_info:
        evaluator.eval()
    assert "stack underflow" in str(exc_info.value).lower()


def test_underflow_divide():
    """/ with one operand raises RpnError."""
    lexer = Lexer("5 /")
    tokens = lexer.tokenize()
    evaluator = Eval(tokens)
    with pytest.raises(RpnError) as exc_info:
        evaluator.eval()
    assert "stack underflow" in str(exc_info.value).lower()
