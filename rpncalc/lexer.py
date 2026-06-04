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
        # Pattern to match positive integers (sequences of digits)
        pattern = r'\d+'
        
        for match in re.finditer(pattern, self.text):
            self.tokens.append(("INT", int(match.group())))
        
        return self.tokens
