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
        for token_type, value in self.tokens:
            if token_type in ("INT", "FLOAT"):
                self.stack.append(value)
            elif token_type == "OP":
                self._apply_op(value)
        
        return self.stack[-1] if self.stack else None

    def _apply_op(self, op: str):
        """Apply an operator to the top of the stack."""
        if len(self.stack) < 2:
            raise RpnError("stack underflow")
        
        b = self.stack.pop()
        a = self.stack.pop()
        
        if op == "+":
            self.stack.append(a + b)
        elif op == "-":
            self.stack.append(a - b)
        elif op == "*":
            self.stack.append(a * b)
        elif op == "/":
            self.stack.append(a / b)
