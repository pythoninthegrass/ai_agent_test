"""Lexer for the rpncalc language."""

import re


class Lexer:
    """Tokenizes input strings into a list of tokens."""

    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.tokens = []

    def tokenize(self) -> list:
        """Return a list of tokens from the input text."""
        # Combined pattern to match floats, integers, variables, or operators
        # Order matters: longer patterns first (** // % == != <= >=), then single char ops (+ - * / < >)
        # Floats: optional minus, digits, dot, digits (e.g., -2.0, 3.14)
        # Integers: optional minus, one or more digits (e.g., -5, 42)
        # Variables: lowercase letters (e.g., x, var, my_var)
        # Keywords: if, else, end
        # Operators: ** // % == != <= >= < > + - * / = (assignment)
        pattern = r'-?\d+\.\d+|-?\d+|[a-z_][a-z0-9_]*|\*\*|//|%|==|!=|<=|>=|<|>|[+\-*/=]'

        for match in re.finditer(pattern, self.text):
            value_str = match.group()
            if value_str in ['if', 'else', 'end']:
                self.tokens.append(("KEYWORD", value_str))
            elif value_str in ['+', '-', '*', '/', '%', '**', '//', '=', '<', '>', '==', '!=', '<=', '>=']:
                self.tokens.append(("OP", value_str))
            elif '.' in value_str:
                self.tokens.append(("FLOAT", float(value_str)))
            elif value_str.isdigit() or (value_str.startswith('-') and value_str[1:].isdigit()):
                self.tokens.append(("INT", int(value_str)))
            elif re.match(r'^-?\d+$', value_str):
                self.tokens.append(("INT", int(value_str)))
            else:
                # It's a variable name
                self.tokens.append(("VAR", value_str))

        return self.tokens
