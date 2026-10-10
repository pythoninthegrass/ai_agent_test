"""Hidden acceptance tests for the rpncalc harness; spec-level only (run_file, RpnError, repl), never shown to the agent."""
import re

import pytest

from adapter import RpnError, drive_repl, run_source


def top(result):
    assert result is not None, "run_file returned None"
    if isinstance(result, (list, tuple)):
        assert result, "run_file returned an empty stack"
        return result[-1]
    return result


@pytest.fixture
def run(tmp_path):
    def _run(src):
        p = tmp_path / "prog.rpn"
        p.write_text(src)
        return top(run_source(str(p), src))

    return _run


@pytest.fixture
def fails(tmp_path):
    def _fails(src):
        p = tmp_path / "prog.rpn"
        p.write_text(src)
        with pytest.raises(RpnError) as exc:
            run_source(str(p), src)
        return str(exc.value)

    return _fails


# milestones 2-4 (lexing, observed through evaluation)
@pytest.mark.parametrize(
    "src,want",
    [
        ("10 20 +", 30),
        ("3.14 2 *", 6.28),
        ("-5 2 +", -3),
        ("5 -3 +", 2),
        ("-2.0 4 *", -8.0),
        ("5 3 -", 2),
        ("  8   2    /  ", 4),
    ],
)
def test_m02_04_lexing(run, src, want):
    assert run(src) == pytest.approx(want)


# milestone 5
@pytest.mark.parametrize(
    "src,want",
    [("3 4 +", 7), ("10 4 -", 6), ("6 7 *", 42), ("20 4 /", 5), ("2 3 4 * +", 14), ("1 2 + 3 4 + *", 21)],
)
def test_m05_arith(run, src, want):
    assert run(src) == want


# milestone 6
def test_m06_true_division_float(run):
    assert run("7 2 /") == 3.5


def test_m06_exact_division_stays_int(run):
    r = run("6 2 /")
    assert r == 3 and type(r) is int


def test_m06_float_multiply(run):
    r = run("1.5 2 *")
    assert r == 3.0 and isinstance(r, float)


def test_m06_mixed_add(run):
    assert run("1 2.5 +") == 3.5


# milestone 7
@pytest.mark.parametrize("src", ["1 0 /", "1.0 0 /", "0 0 /"])
def test_m07_divzero_raises(fails, src):
    assert fails(src).strip()


def test_m07_divzero_message_is_clear(fails):
    assert re.search(r"zero|divi", fails("1 0 /"), re.I)


# milestone 8
@pytest.mark.parametrize("src", ["+", "1 +", "1 2", "1 2 3 +", "* 2 3"])
def test_m08_stack_errors(fails, src):
    fails(src)


# milestone 9
@pytest.mark.parametrize(
    "src,want",
    [("7 3 %", 1), ("2 10 **", 1024), ("7 2 //", 3), ("-7 2 //", -4), ("2 0.5 **", 2**0.5), ("9 4 %", 1)],
)
def test_m09_extended_ops(run, src, want):
    assert run(src) == pytest.approx(want)


# milestone 10
def test_m10_store_and_load(run):
    assert run("5 x =\nx") == 5


def test_m10_reuse(run):
    assert run("5 x = x x +") == 10


def test_m10_reassign(run):
    assert run("1 x = 2 x = x") == 2


def test_m10_derived(run):
    assert run("5 x = x 2 * y =\ny") == 10


def test_m10_unknown_variable(fails):
    fails("nope")


# milestone 11
@pytest.mark.parametrize(
    "src,want",
    [
        ("1 2 <", 1), ("2 1 <", 0), ("2 1 >", 1), ("1 2 >", 0), ("3 3 ==", 1), ("3 4 ==", 0), ("3 4 !=", 1),
        ("3 3 !=", 0), ("3 3 <=", 1), ("4 3 <=", 0), ("4 3 >=", 1), ("3 4 >=", 0), ("1 2 < 3 4 < +", 2), ("2.0 2 ==", 1),
    ],
)
def test_m11_comparisons(run, src, want):
    assert run(src) == want


# milestone 12
@pytest.mark.parametrize(
    "src,want",
    [
        ("1 if 10 else 20 end", 10),
        ("0 if 10 else 20 end", 20),
        ("3 2 > if 100 else 200 end", 100),
        ("1 if 0 if 1 else 2 end else 3 end", 2),
        ("5 x = x 3 > if x 2 * else x end", 10),
        ("2 3 < if\n  7\nelse\n  9\nend", 7),
        ("1 if 1 else 2 end 5 +", 6),
    ],
)
def test_m12_conditionals(run, src, want):
    assert run(src) == want


# milestone 13
@pytest.mark.parametrize(
    "src,want",
    [
        ("# comment\n1 2 +", 3),
        ("1 2 + # trailing", 3),
        ("1\n\n  2\t+", 3),
        ("  1   2    +  \n\n", 3),
        ("# a\n# b\n5", 5),
        ("1 # first\n2 # second\n+ # sum", 3),
    ],
)
def test_m13_comments_whitespace(run, src, want):
    assert run(src) == want


# milestone 14
@pytest.mark.parametrize(
    "src,want",
    [("1 2 swap -", 1), ("5 dup *", 25), ("1 2 drop", 1), ("1 2 over + +", 4), ("2 3 drop dup *", 4), ("1 2 3 drop drop", 1)],
)
def test_m14_stack_ops(run, src, want):
    assert run(src) == want


@pytest.mark.parametrize("src", ["dup", "drop", "1 swap", "1 over"])
def test_m14_stack_ops_underflow(fails, src):
    fails(src)


# milestone 15
@pytest.mark.parametrize(
    "src,want",
    [
        ("def sq dup * end\n5 sq", 25),
        ("def sq dup * end 3 sq 4 sq +", 25),
        ("def inc 1 + end 5 inc inc", 7),
        ("def sq dup * end def quad sq sq end 2 quad", 16),
        ("def sq\n  dup *\nend\n6 sq", 36),
        ("10 k = def addk k + end 5 addk", 15),
    ],
)
def test_m15_functions(run, src, want):
    assert run(src) == want


# milestone 16
def test_m16_repl_prints_top_of_stack():
    assert "7" in drive_repl(["3 4 +", "quit"])


def test_m16_repl_survives_error():
    assert "9" in drive_repl(["1 0 /", "4 5 +", "quit"])


# milestone 17
def test_m17_run_file_program(run):
    assert run("# program\ndef sq dup * end\n5 n =\nn sq\n") == 25


def test_m17_run_file_state_across_lines(run):
    assert run("10 x =\nx 2 *\n") == 20


def test_m17_run_file_multiline_conditional(run):
    assert run("4 x =\nx 3 > if\n  1\nelse\n  0\nend\n") == 1


# milestone 18
@pytest.mark.parametrize(
    "src,line",
    [
        ("5\n0\n/\n", 3),
        ("# c\n\n+", 3),
        ("1 x =\nfoo", 2),
        ("# a\n\n# b\n1\n0 /", 5),
        ("1\n2\n3 4 +\n+ +\n+", 5),
    ],
)
def test_m18_error_line_numbers(fails, src, line):
    assert re.search(rf"\b{line}\b", fails(src))
