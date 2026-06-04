"""Lexer for the rpncalc language."""


class Lexer:
    """Tokenizes input strings into a list of tokens."""

    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.tokens = []

    def tokenize(self) -> list:
        """Return a list of tokens from the input text."""
        return self.tokens
