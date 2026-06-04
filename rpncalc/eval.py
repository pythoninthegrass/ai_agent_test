"""Evaluator for the rpncalc language."""


class RpnError(Exception):
    """Base exception for rpncalc errors."""
    pass


class Eval:
    """Evaluates RPN expressions using a stack."""

    def __init__(self, tokens: list):
        self.tokens = tokens
        self.stack = []

    def eval(self):
        """Evaluate the RPN expression and return the result."""
        return self.stack[-1] if self.stack else None
