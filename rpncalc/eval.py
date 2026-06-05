"""Evaluator for the rpncalc language."""


class RpnError(Exception):
    """Base exception for rpncalc errors."""
    pass


class Eval:
    """Evaluates RPN expressions using a stack."""

    def __init__(self, tokens: list, variables: dict = None, functions: dict = None):
        self.tokens = tokens
        self.stack = []
        self.variables = variables if variables is not None else {}
        self.functions = functions if functions is not None else {}

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
                elif value in self.functions:
                    # Function call - execute the function body
                    func_tokens = self.functions[value]
                    # Pass the current stack to the function evaluator
                    func_eval = Eval(func_tokens, self.variables, self.functions)
                    # The function should see the current stack as its starting point
                    func_eval.stack = self.stack.copy()
                    func_eval.eval()
                    # The function's stack becomes the new state
                    self.stack = func_eval.stack
                    i += 1
                else:
                    # Variable lookup: push the variable's value
                    if value not in self.variables:
                        raise RpnError(f"unknown variable: {value}")
                    self.stack.append(self.variables[value])
                    i += 1
            elif token_type == "OP":
                self._apply_op(value)
                i += 1
            elif token_type == "KEYWORD":
                if value == "if":
                    i = self._eval_if(i)
                elif value == "else":
                    raise RpnError("unexpected 'else' without 'if'")
                elif value == "end":
                    raise RpnError("unexpected 'end' without 'if'")
                elif value == "dup":
                    self._apply_dup()
                    i += 1
                elif value == "swap":
                    self._apply_swap()
                    i += 1
                elif value == "drop":
                    self._apply_drop()
                    i += 1
                elif value == "over":
                    self._apply_over()
                    i += 1
                elif value == "def":
                    i = self._eval_def(i)
            else:
                i += 1

        return self.stack[-1] if self.stack else None

    def _is_truthy(self, value) -> bool:
        """Check if a value is truthy (non-zero numbers are truthy)."""
        if isinstance(value, (int, float)):
            return value != 0
        return bool(value)

    def _find_matching_end(self, start_idx: int, is_def: bool = False) -> int:
        """Find the matching 'end' for an 'if' or 'def' at start_idx.
        
        For 'if': the structure is if true-block [else false-block] end end
        or: if true-block end
        The last 'end' closes the entire if block.
        
        For 'def': the structure is def name ... end
        There's no else for def, so return the first end at depth 0.
        
        Handles nested 'if' blocks by counting depth.
        'def' also counts as a block that needs a matching 'end'.
        
        Returns the index of the matching 'end'."""
        depth = 0
        j = start_idx
        while j < len(self.tokens):
            token_type, value = self.tokens[j]
            if token_type == "KEYWORD" and value in ("if", "def"):
                depth += 1
            elif token_type == "KEYWORD" and value == "end":
                if depth == 0:
                    if is_def:
                        # For def, return the first end at depth 0
                        return j
                    # For if, check if there's an 'else' after this 'end'
                    k = j + 1
                    while k < len(self.tokens):
                        t, v = self.tokens[k]
                        if t == "KEYWORD" and v == "else":
                            # There's an 'else', so continue looking for the second 'end'
                            j = k + 1
                            break
                        elif t == "KEYWORD" and v == "end":
                            # Found another 'end' before 'else'
                            # This is the second end for an if-else block, return it
                            return k
                        k += 1
                    else:
                        # No more tokens, this is the matching end
                        return j
                else:
                    # Found an 'end' at depth > 0, decrement depth
                    depth -= 1
            elif token_type == "KEYWORD" and value == "else":
                # 'else' doesn't affect depth
                pass
            j += 1
        raise RpnError("unclosed conditional block (missing 'end')")

    def _find_else(self, start_idx: int, end_idx: int) -> int:
        """Find 'else' between start_idx and end_idx.
        Returns the index of 'else' or -1 if not found."""
        for j in range(start_idx, end_idx):
            token_type, value = self.tokens[j]
            if token_type == "KEYWORD" and value == "else":
                return j
        return -1

    def _eval_if(self, i: int) -> int:
        """Evaluate an if block starting at index i (the 'if' token).
        Returns the new index after the 'end' token."""
        # Pop the condition
        if len(self.stack) < 1:
            raise RpnError("stack underflow for conditional")
        condition = self.stack.pop()

        # Find the matching 'end' for this 'if'
        end_idx = self._find_matching_end(i + 1, is_def=False)

        # Find 'else' between 'if' and 'end'
        else_idx = self._find_else(i + 1, end_idx)

        if else_idx != -1:
            # There's an 'else' block
            if self._is_truthy(condition):
                # Execute true block (between if and else)
                true_block = self.tokens[i + 1:else_idx]
                evaluator = Eval(true_block, self.variables, self.functions)
                evaluator.eval()
                if evaluator.stack:
                    self.stack.extend(evaluator.stack)
            else:
                # Execute false block (between else and end)
                false_block = self.tokens[else_idx + 1:end_idx]
                evaluator = Eval(false_block, self.variables, self.functions)
                evaluator.eval()
                if evaluator.stack:
                    self.stack.extend(evaluator.stack)
            return end_idx + 1
        else:
            # No 'else' block
            if self._is_truthy(condition):
                true_block = self.tokens[i + 1:end_idx]
                evaluator = Eval(true_block, self.variables, self.functions)
                evaluator.eval()
                if evaluator.stack:
                    self.stack.extend(evaluator.stack)
            else:
                # False condition with no else: push the condition back
                self.stack.append(condition)
            return end_idx + 1

    def _eval_def(self, i: int) -> int:
        """Evaluate a def block starting at index i (the 'def' token).
        Stores the function and returns the index after the 'end' token."""
        # Next token should be the function name (VAR)
        if i + 1 >= len(self.tokens):
            raise RpnError("unexpected end of input after 'def'")
        name_token = self.tokens[i + 1]
        if name_token[0] != "VAR":
            raise RpnError(f"expected function name after 'def', got {name_token[0]}")
        func_name = name_token[1]

        # Find the matching 'end' for this 'def'
        end_idx = self._find_matching_end(i + 2, is_def=True)

        # Store the function body (tokens between def name and end)
        func_body = self.tokens[i + 2:end_idx]
        self.functions[func_name] = func_body

        return end_idx + 1

    def _apply_dup(self):
        """Duplicate the top of stack."""
        if len(self.stack) < 1:
            raise RpnError("stack underflow for dup")
        self.stack.append(self.stack[-1])

    def _apply_swap(self):
        """Swap the top two elements of the stack."""
        if len(self.stack) < 2:
            raise RpnError("stack underflow for swap")
        a = self.stack.pop()
        b = self.stack.pop()
        self.stack.append(a)
        self.stack.append(b)

    def _apply_drop(self):
        """Remove the top of the stack."""
        if len(self.stack) < 1:
            raise RpnError("stack underflow for drop")
        self.stack.pop()

    def _apply_over(self):
        """Duplicate the second element on top of the stack."""
        if len(self.stack) < 2:
            raise RpnError("stack underflow for over")
        self.stack.append(self.stack[-2])

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


def repl(input_stream=None, output_stream=None):
    """Read-Eval-Print Loop for rpncalc.
    
    Reads lines from input_stream (default: stdin), evaluates them,
    prints the top of stack, and exits when 'quit' is entered.
    """
    import sys
    from rpncalc.lexer import Lexer

    if input_stream is None:
        input_stream = sys.stdin
    if output_stream is None:
        output_stream = sys.stdout

    variables = {}
    functions = {}

    while True:
        output_stream.flush()
        try:
            line = input_stream.readline()
        except KeyboardInterrupt:
            output_stream.write("\n")
            output_stream.flush()
            break

        if not line:
            break

        line = line.strip()

        if not line:
            continue

        if line.lower() == "quit":
            break

        try:
            lexer = Lexer(line)
            tokens = lexer.tokenize()
            evaluator = Eval(tokens, variables, functions)
            result = evaluator.eval()

            if evaluator.variables:
                variables = evaluator.variables
            if evaluator.functions:
                functions = evaluator.functions

            if result is not None:
                output_stream.write(f"{result}\n")

        except RpnError as e:
            output_stream.write(f"Error: {e}\n")

        output_stream.flush()
