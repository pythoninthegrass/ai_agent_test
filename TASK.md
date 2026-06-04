# Build `rpncalc` — a stack-based RPN calculator language (TDD)

You are implementing a small interpreted language called **rpncalc** in Python,
test-driven, **one milestone at a time**. The point of this exercise is a long,
honest agentic loop — do NOT try to implement several milestones at once.

## Working rules (follow exactly)

1. Work in the **current directory**. The package lives at `rpncalc/`, tests at `tests/`.
2. Implement **exactly one milestone per iteration**, in order. Never skip ahead.
3. For each milestone:
   a. Write the test file for that milestone FIRST (it should fail).
   b. Run the **full** suite, verbose: `pytest -v`
   c. Implement the feature.
   d. Run the **full** suite again, verbose: `pytest -v` — every prior test must still pass.
   e. If anything is red, fix it and re-run the full suite. Do not proceed until green.
   f. `git add -A && git commit -m "milestone NN: <name>"`
4. Always run `pytest -v` (the whole suite, verbose) — never a single test in isolation.
   Earlier milestones must keep passing; a regression is a failure to fix now.
5. After the final milestone, print a one-line summary: milestones done, total tests, total commits.

## Milestones

1. **scaffold** — `rpncalc/__init__.py`, `rpncalc/lexer.py`, `rpncalc/eval.py`, `tests/`. One trivial passing test that imports the package.
2. **lex-ints** — tokenize positive integers separated by whitespace.
3. **lex-floats-neg** — tokenize floats (`3.14`) and negative numbers (`-5`, `-2.0`).
4. **lex-ops** — tokenize the operators `+ - * /` as distinct tokens from numbers.
5. **eval-arith** — evaluate RPN for `+ - * /` over a stack (`3 4 +` → `7`).
6. **eval-numeric** — preserve int vs float semantics (`7 2 /` → `3.5`; `6 2 /` → `3`).
7. **err-divzero** — division by zero raises `RpnError` with a clear message.
8. **err-stack** — stack underflow (operator with too few operands) and leftover-operands both raise `RpnError`.
9. **ops-extended** — add `% ** //` (modulo, power, floor-div).
10. **variables** — `5 x =` stores; bare `x` pushes its value; unknown var raises `RpnError`.
11. **comparisons** — `< > == != <= >=` push `1`/`0`.
12. **conditionals** — `cond if ... else ... end` blocks (branch on top-of-stack truthiness).
13. **comments-ws** — `#` line comments and arbitrary whitespace/newlines are ignored.
14. **stack-ops** — `dup swap drop over` manipulate the stack.
15. **functions** — `def sq dup * end` defines; `5 sq` calls; recursion-free is fine.
16. **repl** — a `repl()` entrypoint: read a line, eval, print top-of-stack; `quit` exits. Test by feeding lines, not real stdin if simpler.
17. **run-file** — `run_file(path)` executes a `.rpn` program file end to end.
18. **err-lineno** — errors raised from `run_file` include the 1-based line number where they occurred.

Begin with milestone 1.
