"""Evaluator for the rpncalc language."""


class RpnError(Exception):
    """Base exception for rpncalc errors."""
    pass


class Eval:
    """Evaluates RPN expressions using a stack."""

    def __init__(self, tokens: list):
        self.tokens = tokens
        self.stack = []
        self.variables = {}

    def eval(self):
        """Evaluate the RPN expression and return the result."""
        i = 0
        while i < len(self.tokens):
            token_type, value = self.tokens[i]
            
            if token_type in ("INT", "FLOAT"):
                self.stack.append(value)
                i += 1
            elif token_type == "VAR":
                # Check if next token is = (assignment)
                if i + 1 < len(self.tokens) and self.tokens[i + 1] == ("OP", "="):
                    # Assignment: value name = 
                    # Pop the value (which should be on top of stack), then assign
                    i += 2  # Skip VAR and =
                    if len(self.stack) < 1:
                        raise RpnError("stack underflow for assignment")
                    assigned_value = self.stack.pop()
                    self.variables[value] = assigned_value
                else:
                    # Variable lookup: push the variable's value
                    if value not in self.variables:
                        raise RpnError(f"unknown variable: {value}")
                    self.stack.append(self.variables[value])
                    i += 1
            elif token_type == "OP":
                self._apply_op(value)
                i += 1

        # Check for leftover operands
        if len(self.stack) > 1:
            raise RpnError("leftover operands on stack")

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
            if b == 0:
                raise RpnError("division by zero")
            self.stack.append(a / b)
        elif op == "%":
            self.stack.append(a % b)
        elif op == "**":
            self.stack.append(a ** b)
        elif op == "//":
            self.stack.append(a // b)
        elif op == "<":
            self.stack.append(1 if a < b else 0)
        elif op == ">":
            self.stack.append(1 if a > b else 0)
        elif op == "==":
            self.stack.append(1 if a == b else 0)
        elif op == "!=":
            self.stack.append(1 if a != b else 0)
        elif op == "<=":
            self.stack.append(1 if a <= b else 0)
        elif op == ">=":
            self.stack.append(1 if a >= b else 0)
        else:
            raise RpnError(f"unknown operator: {op}")